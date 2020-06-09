'''
Application data structures. Mostly dataclasses inheriting from utils.DataclassSerializer.
'''
from dataclasses import dataclass, field
import datetime
import functools
import json
import hashlib
import os
import pathlib
import shutil
from typing import Any, cast, Dict, List, Optional, Set, Tuple

import click
import dictdiffer
from oauthlib.oauth1 import SIGNATURE_RSA
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1
from tabulate import tabulate

from jira_offline import __title__
from jira_offline.exceptions import (UnableToCopyCustomCACert, InvalidIssuePriority, InvalidIssueStatus,
                                     NoAuthenticationMethod)
from jira_offline.utils import render_field, render_value
from jira_offline.utils.serializer import DataclassSerializer


@dataclass
class CustomFields(DataclassSerializer):
    epic_ref: str = field(default='')
    epic_name: str = field(default='')
    estimate: Optional[str] = field(default='')

    def __bool__(self):
        if self.epic_ref and self.epic_name and self.estimate:
            return True
        return False


@dataclass
class IssueType(DataclassSerializer):
    name: str = field(default='')
    statuses: Set[str] = field(default_factory=set)


@dataclass
class OAuth(DataclassSerializer):
    access_token: Optional[str] = field(default=None)
    access_token_secret: Optional[str] = field(default=None)
    consumer_key: Optional[str] = field(default=None)
    key_cert: Optional[str] = field(default=None)

    def asoauth1(self) -> OAuth1:
        '''
        Return an OAuth1 object compatible with requests
        '''
        return OAuth1(
            self.consumer_key,
            rsa_key=self.key_cert,
            signature_method=SIGNATURE_RSA,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret,
        )


@dataclass  # pylint: disable=too-many-instance-attributes
class ProjectMeta(DataclassSerializer):  # pylint: disable=too-many-instance-attributes
    key: str
    name: Optional[str] = field(default=None)
    username: Optional[str] = field(default=None)
    password: Optional[str] = field(default=None)
    protocol: Optional[str] = field(default='https')
    hostname: Optional[str] = field(default='jira.atlassian.com')
    last_updated: Optional[str] = field(default=None)
    issuetypes: Dict[str, IssueType] = field(default_factory=dict)
    custom_fields: CustomFields = field(default_factory=CustomFields)
    priorities: Set[str] = field(default_factory=set)
    components: Set[str] = field(default_factory=set)
    oauth: Optional[OAuth] = field(default=None)
    ca_cert: Optional[str] = field(default=None)
    timezone: Optional[str] = field(default=None)

    @property
    def jira_server(self):
        return f'{self.protocol}://{self.hostname}'

    @property
    def auth(self):
        if self.username:
            return HTTPBasicAuth(self.username, self.password)
        elif self.oauth:
            return self.oauth.asoauth1()
        else:
            raise NoAuthenticationMethod

    @property
    def project_uri(self):
        return f'{self.jira_server}/{self.key}'

    @property
    def id(self) -> str:
        return hashlib.sha1(self.project_uri.encode('utf8')).hexdigest()

    def set_ca_cert(self, ca_cert: str):
        '''
        Copy supplied ca_cert file path into application config directory
        '''
        # ensure config path exists
        pathlib.Path(click.get_app_dir(__title__)).mkdir(parents=True, exist_ok=True)

        target_ca_cert_path = os.path.join(click.get_app_dir(__title__), f'{self.id}.ca_cert')

        try:
            shutil.copyfile(ca_cert, target_ca_cert_path)
            self.ca_cert = target_ca_cert_path
        except IOError as e:
            # permission denied etc
            raise UnableToCopyCustomCACert(str(e))

    def render(self) -> List[Tuple[str, str]]:
        '''
        Pretty print this project
        '''
        def fmt(field_name: str) -> Tuple[str, str]:
            '''
            Params:
                field_name: Dataclass field being formatted
            Returns:
                Formatted text
            '''
            return render_field(ProjectMeta, field_name, getattr(self, field_name))

        if self.oauth:
            auth = f'oauth_key={self.oauth.consumer_key}'
        else:
            auth = f'username={self.username}, password=****'

        attrs = [
            fmt('name'),
            fmt('key'),
            ('Project URI', self.project_uri),
            ('Auth', auth),
            ('Issue Types', render_value(list(self.issuetypes.keys()))),
            ('Components', render_value(self.components)),
            fmt('last_updated'),
        ]
        return attrs

    def __str__(self) -> str:
        '''
        Render project to friendly string
        '''
        return tabulate(self.render())


@dataclass
class AppConfig(DataclassSerializer):
    schema_version: int = field(default=2)
    projects: Dict[str, ProjectMeta] = field(default_factory=dict)

    def write_to_disk(self):
        # ensure config path exists
        pathlib.Path(click.get_app_dir(__title__)).mkdir(parents=True, exist_ok=True)

        # late import to avoid circular dependency
        from jira_offline.config import get_config_filepath  # pylint: disable=import-outside-toplevel, cyclic-import
        with open(get_config_filepath(), 'w') as f:
            json.dump(self.serialize(), f)
            f.write('\n')


@dataclass  # pylint: disable=too-many-instance-attributes
class Issue(DataclassSerializer):  # pylint: disable=too-many-instance-attributes
    project_id: str = field(metadata={'friendly': 'Project ID', 'readonly': True})
    issuetype: str = field(metadata={'friendly': 'Type', 'readonly': True})
    project: str = field(metadata={'readonly': True})
    summary: str
    assignee: Optional[str] = field(default=None)
    created: Optional[datetime.datetime] = field(default=None, metadata={'readonly': True})
    creator: Optional[str] = field(default=None, metadata={'readonly': True})
    epic_name: Optional[str] = field(default=None, metadata={'friendly': 'Epic Short Name'})
    epic_ref: Optional[str] = field(default=None)
    estimate: Optional[int] = field(default=None)
    description: Optional[str] = field(default=None)
    fixVersions: Optional[set] = field(default=None, metadata={'friendly': 'Fix Version'})
    components: Optional[set] = field(default=None)
    id: Optional[str] = field(default=None, metadata={'readonly': True})
    key: Optional[str] = field(default=None, metadata={'readonly': True})
    labels: Optional[set] = field(default=None)
    _priority: Optional[str] = field(
        default=None, metadata={'friendly': 'Priority', 'property': 'priority'}
    )
    reporter: Optional[str] = field(default=None)
    _status: Optional[str] = field(
        default=None, metadata={'friendly': 'Status', 'property': 'status', 'readonly': True}
    )
    updated: Optional[datetime.datetime] = field(default=None, metadata={'readonly': True})

    # local-only dict which represents serialized Issue last seen on Jira server
    # this property is not written to cache and is created at runtme from diff_to_original
    original: Dict[str, Any] = field(default_factory=dict, metadata={'rw': ''})

    # patch of current Issue to dict last seen on Jira server
    # "rw" flag instructs serializer to deserialize this only; do not include during serialize()
    diff_to_original: Optional[list] = field(default=None, metadata={'rw': 'r'})

    project_ref: Optional[ProjectMeta] = field(default=None, metadata={'rw': ''})

    @classmethod
    @functools.lru_cache(maxsize=1)
    def blank(cls):
        '''
        Static class property returning a blank/empty Issue
        '''
        blank_issue = Issue(project_id='', project='', issuetype='', summary='', description='')
        blank_issue.original = blank_issue.serialize()
        return blank_issue

    @property
    def priority(self) -> Optional[str]:
        return self._priority

    @priority.setter
    def priority(self, value: str):
        if not self.project_ref:
            raise Exception

        if value not in self.project_ref.priorities:
            raise InvalidIssuePriority(', '.join(self.project_ref.priorities))

        self._priority = value

    @property
    def status(self) -> Optional[str]:
        return self._status

    @status.setter
    def status(self, value: str):
        if not self.project_ref:
            raise Exception

        if value not in self.project_ref.issuetypes[self.issuetype].statuses:
            raise InvalidIssueStatus(
                ', '.join(self.project_ref.issuetypes[self.issuetype].statuses)
            )

        self._status = value

    @property
    def exists(self) -> bool:
        '''
        Return True if Issue exists on Jira, or False if it's local only
        '''
        return bool(self.id)

    def diff(self, data: dict=None) -> Optional[list]:
        '''
        If this Issue object has the original property set, render the diff between self and
        the original property. This is written to storage to track changes made offline.

        Params:
            data:  Serialized dict of self (can be passed to avoid double-call to serialize)
        Returns:
            Return from dictdiffer.diff to be stored in Issue.diff_to_original property
        '''
        if not self.original:
            return None

        if not data:
            data = self.serialize()

        return list(dictdiffer.diff(data, self.original, ignore=set(['diff_to_original'])))

    @classmethod
    def deserialize(cls, attrs: dict, project_ref: Optional[ProjectMeta]=None) -> 'Issue':  # pylint: disable=arguments-differ
        '''
        Deserialize a dict into an Issue object. Inflate the original Jira issue from the
        diff_to_original property.

        Params:
            attrs:  Dict to deserialize into an Issue
        Returns:
            List from dictdiffer.diff for Issue.diff_to_original property
        '''
        # deserialize supplied dict into an Issue object
        issue = cast(Issue, super().deserialize(attrs))

        if issue.diff_to_original is None:
            issue.diff_to_original = []

        # if issue exists on Jira server (see `exists` property above)
        if bool(attrs.get('id')):
            # apply the diff_to_original patch to the serialized version of the issue, which
            # recreates the issue dict as last seen on the Jira server
            issue.original = dictdiffer.patch(issue.diff_to_original, issue.serialize())

        # store reference to Jira project this Issue belongs to
        issue.project_ref = project_ref

        return issue


    def render(self, conflicts: dict=None, modified_fields: set=None) -> List[Tuple[str, str]]:
        '''
        Pretty print this Issue. When `conflicts` is passed, render attributes as

        Params:
            conflicts:        Render conflicting attributes in the git-style
            modified_fields:  Render coloured output for fields which have been modified
        '''
        def fmt(field_name: str, prefix: str=None) -> Tuple:
            '''
            Pretty formatting with support for diffing and conflicts

            Params:
                field_name:  Dataclass field being formatted
                prefix:      A prefix to prepend in front of the field's value
            Returns:
                Tuple of formatted-pair tuples
            '''
            if conflicts and field_name in conflicts:
                return (
                    ('<<<<<<< base', ''),
                    render_field(Issue, field_name, conflicts[field_name]['base'], value_prefix=prefix),
                    ('=======', ''),
                    render_field(Issue, field_name, conflicts[field_name]['updated'], value_prefix=prefix),
                    ('>>>>>>> updated', ''),
                )

            elif modified_fields and field_name in modified_fields:
                # render the old version in red with a minus
                old_value = self.original.get(field_name)
                if old_value:
                    old_field = render_field(Issue, field_name, old_value, title_prefix='-',
                                             value_prefix=prefix, color='red')
                # render the new version in green with a plus
                new_value = getattr(self, field_name)
                if new_value:
                    new_field = render_field(Issue, field_name, new_value, title_prefix='+',
                                             value_prefix=prefix, color='green')
                if old_value and new_value:
                    return (old_field, new_field)
                elif old_value:
                    return (old_field,)
                else:
                    return (new_field,)

            else:
                return (render_field(Issue, field_name, getattr(self, field_name), title_prefix='\u2800',
                                     value_prefix=prefix),)

        if self.issuetype == 'Epic':
            epicdetails = fmt('epic_name')
        else:
            epicdetails = fmt('epic_ref')

        return [
            *fmt('summary', prefix=f'[{self.key}] '),
            *fmt('issuetype'),
            *epicdetails,
            *fmt('status'),
            *fmt('_priority'),
            *fmt('assignee'),
            *fmt('estimate'),
            *fmt('description'),
            *fmt('fixVersions'),
            *fmt('labels'),
            *fmt('components'),
            *fmt('reporter'),
            *fmt('creator'),
            *fmt('created'),
            *fmt('updated'),
        ]

    def as_json(self) -> str:
        '''
        Render issue as JSON
        '''
        return json.dumps(self.serialize())

    def __str__(self) -> str:
        '''
        Render issue to friendly string
        '''
        return tabulate(self.render())

'''
Application data structures. Mostly dataclasses inheriting from utils.DataclassSerializer.
'''
from dataclasses import dataclass, field
import datetime
import enum
import functools
import json
import hashlib
import os
import pathlib
import textwrap
from typing import Any, Dict, Optional, Set, Tuple

import arrow
import click
import dictdiffer
from oauthlib.oauth1 import SIGNATURE_RSA
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1
from tabulate import tabulate

from jira_cli import __title__
from jira_cli.exceptions import IssuePriorityInvalid, NoAuthenticationMethod
from jira_cli.utils import classproperty, friendly_title, get_field_by_name
from jira_cli.utils.serializer import DataclassSerializer, get_enum, get_type_class


@dataclass
class CustomFields(DataclassSerializer):
    epic_ref: str = field(default='')
    epic_name: str = field(default='')
    estimate: str = field(default='')

    def __bool__(self):
        if self.epic_ref and self.epic_name and self.estimate:
            return True
        return False


@dataclass
class IssueType(DataclassSerializer):
    name: str = field(default='')
    priorities: Set[str] = field(default_factory=set)


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
    custom_fields: CustomFields = field(default_factory=CustomFields)  # type: ignore
    oauth: Optional[OAuth] = field(default=None)

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


@dataclass
class AppConfig(DataclassSerializer):
    projects: Dict[str, ProjectMeta] = field(default_factory=dict)

    def write_to_disk(self):
        # ensure config path exists
        pathlib.Path(click.get_app_dir(__title__)).mkdir(parents=True, exist_ok=True)

        config_filepath = os.path.join(click.get_app_dir(__title__), 'app.json')
        with open(config_filepath, 'w') as f:
            json.dump(self.serialize(), f)
            f.write('\n')


class IssueStatus(enum.Enum):
    Backlog = 'Backlog'
    ToDo = 'To Do'
    InProgress = 'In Progress'
    StoryInProgress = 'Story in Progress'
    EpicInProgress = 'Epic in Progress'
    EpicInReview = 'Epic in Review'
    EpicWithSquad = 'Epic with Squad'
    EpicReadyforSquad = 'Epic Ready for Squad'
    InRelease = 'In Release'
    InTest = 'In Test'
    Done = 'Done'
    StoryDone = 'Story Done'
    EpicDone = 'Epic Done'
    Closed = 'Closed'
    RiskClosed = 'Risk Closed'
    RiskIdentified = 'Risk Identified'
    NotAssessed = 'Not Assessed'
    Resolved = 'Resolved'
    Accepted = 'Accepted'
    Blocked = 'Blocked'
    Unspecified = 'n/a'


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
    id: Optional[str] = field(default=None, metadata={'readonly': True})
    key: Optional[str] = field(default=None, metadata={'readonly': True})
    labels: Optional[set] = field(default=None)
    _priority: Optional[str] = field(default=None, metadata={'friendly': 'Priority', 'property': 'priority'})
    reporter: Optional[str] = field(default=None)
    status: Optional[IssueStatus] = field(default=None, metadata={'readonly': True})
    updated: Optional[datetime.datetime] = field(default=None, metadata={'readonly': True})

    # local-only dict which represents serialized Issue last seen on Jira server
    # this property is not written to cache and is created at runtme from diff_to_original
    original: Dict[str, Any] = field(default_factory=dict, repr=False)

    # patch of current Issue to dict last seen on Jira server
    diff_to_original: Optional[list] = field(default=None, repr=False)

    project_ref: Optional[ProjectMeta] = field(default=None, repr=False)

    @classproperty
    @functools.lru_cache(maxsize=1)
    def blank(self):
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

        if value not in self.project_ref.issuetypes[self.issuetype].priorities:
            raise IssuePriorityInvalid(
                ', '.join(self.project_ref.issuetypes[self.issuetype].priorities)
            )

        self._priority = value

    @property
    def exists(self) -> bool:
        '''
        Return True if Issue exists on Jira, or False if it's local only
        '''
        return bool(self.id)

    @property
    def is_open(self) -> bool:
        if self.is_inprogress or self.is_todo:
            return True
        elif self.is_done or self.is_closed or self.status == IssueStatus.Unspecified:
            return False
        else:
            raise AttributeError('Issue cannot be determined open or closed!')

    @property
    def is_todo(self) -> bool:
        if self.status in (IssueStatus.Backlog, IssueStatus.ToDo, IssueStatus.RiskIdentified,
                           IssueStatus.NotAssessed, IssueStatus.EpicReadyforSquad):
            return True
        return False

    @property
    def is_inprogress(self) -> bool:
        if self.status in (IssueStatus.InProgress, IssueStatus.InRelease, IssueStatus.Accepted,
                           IssueStatus.EpicInProgress, IssueStatus.StoryInProgress,
                           IssueStatus.EpicWithSquad, IssueStatus.EpicInReview):
            return True
        return False

    @property
    def is_done(self) -> bool:
        if self.status in (IssueStatus.Done, IssueStatus.StoryDone, IssueStatus.EpicDone,
                           IssueStatus.Resolved):
            return True
        return False

    @property
    def is_closed(self) -> bool:
        if self.is_done or self.status in (IssueStatus.Closed, IssueStatus.RiskClosed):
            return True
        return False

    def diff(self, data: dict=None) -> Optional[list]:
        '''
        If this Issue object has the original property set, render the diff between self and
        the original property. This is written to storage to track changes made offline.

        Params:
            data (optional):  Serialized dict of self (can be passed to avoid double-call to serialize)
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
        issue = super().deserialize(attrs)

        if issue.diff_to_original is None:  # pylint: disable=no-member
            issue.diff_to_original = []

        # if issue exists on Jira server (see `exists` property above)
        if bool(attrs.get('id')):
            # apply the diff_to_original patch to the serialized version of the issue, which
            # recreates the issue dict as last seen on the Jira server
            issue.original = dictdiffer.patch(issue.diff_to_original, issue.serialize())  # pylint: disable=no-member

        # store reference to Jira project this Issue belongs to
        issue.project_ref = project_ref

        return issue

    def __str__(self, conflicts: dict=None):
        '''
        Pretty print this Issue

        Params:
            conflicts:  A conflict object
        '''
        def fmt(field_name: str, prefix: str=None) -> Tuple:
            '''
            Pretty formatting with support for conflicts

            Params:
                field_name: Dataclass field being formatted
                prefix:     Arbitrary prefix to prepend during string format
            Returns:
                Tuple of formatted-pair tuples
            '''
            if conflicts and field_name in conflicts:
                return (
                    ('<<<<<<< base', ''),
                    render(field_name, conflicts[field_name]['base'], prefix),
                    ('=======', ''),
                    render(field_name, conflicts[field_name]['updated'], prefix),
                    ('>>>>>>> updated', ''),
                )
            else:
                return (render(field_name, getattr(self, field_name), prefix),)

        def render(field_name: str, value: Any, prefix: str=None) -> Tuple[str, str]:
            '''
            Single-field pretty formatting function supporting various types

            Params:
                field_name: Dataclass field to render
                value:      Data to be rendered according to format
                prefix:     Arbitrary prefix to prepend during string format
            Returns:
                Pretty field title, formatted value
            '''
            title = friendly_title(field_name)

            # determine the origin type for this field (thus handling Optional[type])
            type_ = get_type_class(get_field_by_name(field_name).type)

            if value is None:
                value = ''
            elif type_ is set:
                value = tabulate([('-', v) for v in value], tablefmt='plain')
            elif type_ is datetime.datetime:
                dt = arrow.get(self.created)
                value = f'{dt.humanize()} [{dt.format()}]'
            elif get_enum(type_):
                value = value.value
            elif value and type_ is str and len(value) > 100:
                value = '\n'.join(textwrap.wrap(value, width=100))

            if prefix:
                value = f'{prefix} {value}'

            return title, value

        if self.issuetype == 'Epic':
            epicdetails = fmt('epic_name')
        else:
            epicdetails = fmt('epic_ref')

        attrs = [
            *fmt('summary', prefix=f'[{self.key}]'),
            *fmt('issuetype'),
            *epicdetails,
            *fmt('status'),
            *fmt('_priority'),
            *fmt('assignee'),
            *fmt('estimate'),
            *fmt('description'),
            *fmt('fixVersions'),
            *fmt('labels'),
            *fmt('reporter'),
            *fmt('creator'),
            *fmt('created'),
            *fmt('updated'),
        ]
        return tabulate(attrs)

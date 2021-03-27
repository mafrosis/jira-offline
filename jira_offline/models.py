'''
Application data structures. Mostly dataclasses inheriting from utils.DataclassSerializer.
'''
import dataclasses
from dataclasses import dataclass, field
import datetime
import decimal
import functools
import json
import hashlib
import os
import pathlib
import shutil
from typing import Any, cast, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
from urllib.parse import urlparse

import click
import dictdiffer
from oauthlib.oauth1 import SIGNATURE_RSA
import pandas as pd
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1
import pytz
from tabulate import tabulate
from tzlocal import get_localzone

from jira_offline import __title__
from jira_offline.exceptions import (BadProjectMetaUri, CannotSetIssueAttributeDirectly,
                                     UnableToCopyCustomCACert, NoAuthenticationMethod)
from jira_offline.utils import get_field_by_name, render_field, render_value
from jira_offline.utils.serializer import DataclassSerializer, get_base_type

if TYPE_CHECKING:
    from jira_offline.jira import Jira  # pylint: disable=cyclic-import


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
        '''Return an OAuth1 object compatible with requests'''
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
    components: Optional[Set[str]] = field(default_factory=set)  # type: ignore[assignment]
    oauth: Optional[OAuth] = field(default=None)
    ca_cert: Optional[str] = field(default=None)
    timezone: datetime.tzinfo = field(default=get_localzone())

    # reference to parent AppConfig class
    config: Optional['AppConfig'] = field(default=None, metadata={'serialize': False})

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

    @classmethod
    def factory(cls, project_uri: str, timezone: Optional[str]=None) -> 'ProjectMeta':
        uri = urlparse(project_uri)

        if not uri.scheme or not uri.netloc or not uri.path:
            raise BadProjectMetaUri

        return ProjectMeta(
            key=uri.path[1:],
            protocol=uri.scheme,
            hostname=uri.netloc,
            timezone=pytz.timezone(timezone) if timezone else get_localzone(),
        )

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
        '''Render object as a raw list of tuples'''

        def fmt(field_name: str) -> Tuple[str, str]:
            '''Helper simply wrapping `render_field` for this class'''
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
        '''Render project to friendly string'''
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
    project: ProjectMeta = field(repr=False, metadata={'serialize': False})
    summary: str

    assignee: Optional[str] = field(default=None)
    created: Optional[datetime.datetime] = field(default=None, metadata={'readonly': True})
    creator: Optional[str] = field(default=None, metadata={'readonly': True})
    epic_name: Optional[str] = field(default=None, metadata={'friendly': 'Epic Short Name'})
    epic_ref: Optional[str] = field(default=None)
    estimate: Optional[decimal.Decimal] = field(default=None)
    description: Optional[str] = field(default=None)
    fix_versions: Optional[set] = field(default_factory=set, metadata={'friendly': 'Fix Version'})
    components: Optional[set] = field(default_factory=set)
    id: Optional[int] = field(default=None, metadata={'readonly': True})
    key: Optional[str] = field(default=None, metadata={'readonly': True})
    labels: Optional[set] = field(default_factory=set)
    priority: Optional[str] = field(default=None, metadata={'friendly': 'Priority'})
    reporter: Optional[str] = field(default=None)
    status: Optional[str] = field(default=None, metadata={'friendly': 'Status', 'readonly': True})
    updated: Optional[datetime.datetime] = field(default=None, metadata={'readonly': True})

    # dict which represents serialized Issue last seen on Jira server
    # this attribute is not written to cache, and is created at runtime from Issue.diff_to_original
    original: Dict[str, Any] = field(
        init=False, repr=False, default_factory=dict, metadata={'serialize': False}
    )

    # patch of current Issue to dict last seen on Jira server
    diff_to_original: Optional[list] = field(default_factory=list)

    _active: bool = field(init=False, repr=False, default=False, metadata={'serialize': False})
    modified: Optional[bool] = field(default=False)


    def __post_init__(self):
        '''
        Special dataclass dunder method called automatically after Issue.__init__
        '''
        # apply the diff_to_original patch to the serialized version of the issue, which
        # recreates the issue dict as last seen on the Jira server
        self.set_original(
            dictdiffer.patch(self.diff_to_original if self.diff_to_original else [], self.serialize())
        )

        # Mark this Issue as active, which means that any subsequent modifications to the Issue object
        # attributes will result in the modified flag being set (see __setattr__).
        self.__dict__['_active'] = True


    def __setattr__(self, name, value):
        '''
        Override __setattr__ dunder method to ensure Issue.modified is set on change.

        Using Issue._active is necessary as __setattr__ is called repeatedly during object creation.
        The modified flag must track changes made _after_ the Issue object has been created.

        Issue.modified is not relevant for _new_ issues, which have not yet been sync'd to Jira.
        '''
        if self._active:
            if name == 'original':
                raise CannotSetIssueAttributeDirectly

            # modified is only set to true if this issue exists on the Jira server
            self.__dict__['modified'] = bool(self.exists)

        self.__dict__[name] = value


    def set_original(self, value: Dict[str, Any]):
        '''
        Special setter method for Issue.original, which ensures that changing this attribute does not
        also result in Issue.modified being set to true
        '''
        if not self.exists:
            return

        if 'diff_to_original' in value:
            del value['diff_to_original']
        if 'modified' in value:
            del value['modified']

        # write self.original without setting the modified flag
        self.__dict__['original'] = value


    def commit(self):
        '''
        Commit this Issue's changes back into the central Jira class storage. Using this method
        ensures the Issue's diff is correctly persisted along with any edits.
        '''
        # Refresh the Issue.diff_to_original property before the commit
        self.diff()

        from jira_offline.jira import jira  # pylint: disable=import-outside-toplevel, cyclic-import

        # commit the Issue into the Jira class DataFrame
        jira[self.key] = self


    @property
    def project_key(self) -> str:
        return self.project.key

    @classmethod
    @functools.lru_cache(maxsize=1)
    def blank(cls):
        '''
        Static class property returning a blank/empty Issue
        '''
        return Issue(
            project_id='', project=ProjectMeta(key=''), issuetype='', summary='', description=''
        )

    @property
    def exists(self) -> bool:
        '''
        Return True if Issue exists on Jira, or False if it's local only
        '''
        return bool(self.id)

    def diff(self) -> list:
        '''
        If this Issue object has the original property set, render the diff between self and
        the original property. This is written to storage to track changes made offline.

        Params:
            data:  Serialized dict of self (can be passed to avoid double-call to serialize)
        Returns:
            Return from dictdiffer.diff to be stored in Issue.diff_to_original property
        '''
        if not self.exists:
            return []

        if not self.original:
            raise Exception

        diff = list(
            dictdiffer.diff(
                self.serialize(),
                self.original,
                ignore=set(['diff_to_original', 'modified'])
            )
        )
        # Write self.diff_to_original without setting the modified flag
        self.__dict__['diff_to_original'] = diff

        return self.diff_to_original or []

    @classmethod
    def deserialize(cls, attrs: dict, project: Optional[ProjectMeta]=None,  # type: ignore[override] # pylint: disable=arguments-differ
                    ignore_missing: bool=False) -> 'Issue':
        '''
        Deserialize a dict into an Issue object. Inflate the _original_ version of the object from the
        Issue.diff_to_original field which is written to the cache.

        Params:
            attrs:           Dict to deserialize into an Issue
            project:         Reference to Jira project this Issue belongs to
            ignore_missing:  Ignore missing mandatory fields during deserialisation
        Returns:
            List from dictdiffer.diff for Issue.diff_to_original property
        '''
        # deserialize supplied dict into an Issue object
        # use `cast` to cover the mypy typecheck errors the arise from polymorphism
        return cast(
            Issue,
            super().deserialize(
                attrs,
                project.timezone if project else None,
                ignore_missing=ignore_missing,
                constructor_kwargs={'project': project},
            )
        )


    def render(self, conflicts: dict=None, modified_fields: set=None) -> List[Tuple[str, str]]:
        '''
        Render object as a raw list of tuples.

        Params:
            conflicts:        Render conflicting fields in the style of git-merge
            modified_fields:  Render modified fields with colours in the style of git-diff
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
            *fmt('priority'),
            *fmt('assignee'),
            *fmt('estimate'),
            *fmt('description'),
            *fmt('fix_versions'),
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


    def to_series(self) -> pd.Series:
        '''
        Render issue as a Pandas Series object
        '''
        attrs = {k:v for k,v in self.__dict__.items() if k not in ('project', '_active')}
        attrs['project_key'] = self.project.key if self.project else None

        # Render diff_to_original and original as strings when stored in a DataFrame
        for col in ('diff_to_original', 'original'):
            attrs[col] = json.dumps(attrs[col])

        # convert Issue.estimates to string
        if attrs['estimate']:
            attrs['estimate'] = str(attrs['estimate'])

        series = pd.Series(attrs).fillna(value=get_issue_field_defaults_for_pandas())

        # convert all datetimes to UTC, where they are non-null (which is all non-new issues)
        for col in ('created', 'updated'):
            series[col] = pd.Timestamp(series[col]).tz_convert('UTC')

        return series


    @classmethod
    def from_series(cls, series: pd.Series, project: Optional[ProjectMeta]=None) -> 'Issue':
        '''
        Convert Pandas Series object into an Issue
        '''
        attrs = series.to_dict()

        # Set the project attribute, and drop the project_key field from the dataframe
        attrs['project'] = project
        del attrs['project_key']

        # Remove the original attribute before the Issue constructor call
        original = attrs.pop('original', None)

        # Use pandas default mapping to map back to dataclass defaults
        null_defaults = get_issue_field_defaults_for_pandas()

        def convert(key, value):
            f = get_field_by_name(Issue, key)
            typ_ = get_base_type(f.type)

            if value == null_defaults.get(key):
                return f.default
            elif typ_ is datetime.datetime:
                return value.tz_convert(project.timezone).to_pydatetime()
            elif typ_ is decimal.Decimal:
                return decimal.Decimal(value)
            else:
                return value

        attrs = {k:convert(k, v) for k,v in attrs.items()}

        if attrs['diff_to_original']:
            attrs['diff_to_original'] = json.loads(attrs['diff_to_original'])

        issue = Issue(**attrs)

        if original:
            issue.set_original(json.loads(original))

        return issue


    def __str__(self) -> str:
        '''
        Render issue to friendly string
        '''
        return tabulate(self.render())


@functools.lru_cache()
def get_issue_field_defaults_for_pandas() -> Dict[str, str]:
    '''
    Return a mapping of Issue.field_name->default, where the default is compatible with pandas
    '''
    attrs = dict()
    for f in dataclasses.fields(Issue):
        if not isinstance(f.default, dataclasses._MISSING_TYPE):  # pylint: disable=protected-access
            typ_ = get_base_type(f.type)

            if typ_ is datetime.datetime:
                attrs[f.name] = pd.to_datetime(0).tz_localize('utc')
            elif typ_ is decimal.Decimal:
                attrs[f.name] = ''
            else:
                attrs[f.name] = typ_()
    return attrs


@dataclass
class IssueFilter:
    '''
    Encapsulates any filters passed in via CLI

    When the application is invoked on the CLI, filters are set via user-supplied arguments. An
    instance of this class is created on the central Jira object, and any filters are configured.

    The `items`, `keys` or `values` methods on the Jira class will return issues respecting these
    filters.
    '''
    project_key: Optional[str] = field(default=None)

    def __init__(self, jira_):
        self.jira = jira_

    def apply(self) -> pd.DataFrame:
        '''Compare passed Issue object against the class attributes'''
        filters = {}

        if self.project_key:
            filters['project_key'] = self.project_key

        if not filters:
            return self.jira._df  # pylint: disable=protected-access

        return self.jira._df.query(' & '.join([f'{k}=="{v}"' for k,v in filters.items()]))  # pylint: disable=protected-access

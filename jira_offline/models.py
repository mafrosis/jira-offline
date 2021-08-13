'''
Application data structures. Mostly dataclasses inheriting from utils.DataclassSerializer.
'''
from dataclasses import asdict, dataclass, field
import datetime
import decimal
import functools
import json
import hashlib
import os
import pathlib
import shutil
from typing import Any, cast, Dict, Generator, Iterator, List, Optional, Set, Tuple
from urllib.parse import urlparse

import click
import dictdiffer
from oauthlib.oauth1 import SIGNATURE_RSA
import pandas as pd
import pytz
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1
from tabulate import tabulate
from tzlocal import get_localzone

from jira_offline import __title__
from jira_offline.exceptions import (BadProjectMetaUri, CannotSetIssueOriginalDirectly,
                                     UnableToCopyCustomCACert, NoAuthenticationMethod)
from jira_offline.utils import (get_dataclass_defaults_for_pandas, get_field_by_name, render_field,
                                render_value)
from jira_offline.utils.convert import preprocess_sprint
from jira_offline.utils.serializer import DataclassSerializer, get_base_type

# pylint: disable=too-many-instance-attributes


@dataclass
class CustomFields(DataclassSerializer):
    '''
    CustomFields are dynamic fields defined per-project on Jira. This class tracks the mapping of the
    field name, such as `epic_link`, back to the underlying Jira customfield name, such as
    `customfield_10100`.

    Each customfield name defined in this class will match 1-1 with an identically named attribute on
    the Issue class.
    '''
    # Default set of customfields from Jira
    epic_link: Optional[str] = field(
        default='', metadata={'cli_help': 'Epic key this issue is related to'}
    )
    epic_name: Optional[str] = field(
        default='', metadata={'cli_help': 'Short epic name'}
    )
    sprint: Optional[str] = field(
        default='', metadata={'cli_help': 'Sprint number', 'parse_func': preprocess_sprint}
    )

    # Additional special-case customfields defined in this application
    story_points: Optional[str] = field(
        default='', metadata={'cli_help': 'Complexity estimate in story points'}
    )
    parent_link: Optional[str] = field(
        default='', metadata={'cli_help': 'Link to a non-epic parent issue, such as Feature or Theme'}
    )

    # Extended set of user-defined customfields
    extended: Optional[Dict[str, str]] = field(default_factory=dict)  # type: ignore[assignment]


    def items(self) -> Iterator:
        'Iterate the customfields set for the associated project, plus user-defined ones in self.extended'
        attrs = {k:v for k,v in asdict(self).items() if v}
        if self.extended:
            del attrs['extended']
            for k,v in self.extended.items():
                attrs[f'extended.{k}'] = v
        return iter(attrs.items())

    def __getitem__(self, key: str) -> str:
        '''
        Get attribute on this object by key, like a dict. Transparently maps keys into the extended
        sub-dict if `key` does not exist as an attribute.
        '''
        try:
            return str(getattr(self, key))
        except AttributeError:
            if self.extended:
                return self.extended[key]
            raise KeyError

    def __str__(self):
        return render_value(dict(self.items()))


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


@dataclass
class ProjectMeta(DataclassSerializer):
    key: str
    name: Optional[str] = field(default=None)
    username: Optional[str] = field(default=None)
    password: Optional[str] = field(default=None)
    protocol: Optional[str] = field(default='https')
    hostname: Optional[str] = field(default='jira.atlassian.com')
    last_updated: Optional[str] = field(default=None, metadata={'friendly': 'Last Sync'})
    issuetypes: Dict[str, IssueType] = field(default_factory=dict)
    customfields: Optional[CustomFields] = field(default=None)
    priorities: Optional[Set[str]] = field(default_factory=set)  # type: ignore[assignment]
    components: Optional[Set[str]] = field(default_factory=set)  # type: ignore[assignment]
    oauth: Optional[OAuth] = field(default=None)
    ca_cert: Optional[str] = field(default=None)
    timezone: datetime.tzinfo = field(default=get_localzone())
    jira_id: Optional[str] = field(default=None)

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
            ('Priorities', render_value(self.priorities)),
            ('Customfields', str(self.customfields)),
            fmt('components'),
            fmt('timezone'),
            fmt('last_updated'),
        ]
        return attrs

    def __str__(self) -> str:
        '''Render project to friendly string'''
        return tabulate(self.render())


@dataclass
class AppConfig(DataclassSerializer):
    schema_version: int = field(default=3)
    user_config_filepath: str = field(default='')
    projects: Dict[str, ProjectMeta] = field(default_factory=dict)

    @dataclass
    class Sync:
        page_size: int = field(default=25)

    sync: Sync = field(init=False, metadata={'serialize': False})

    @dataclass
    class Display:
        ls_fields: List[str]
        ls_fields_verbose: List[str]
        ls_default_filter: str

    display: Display = field(init=False, metadata={'serialize': False})

    customfields: Dict[str, dict] = field(init=False, metadata={'serialize': False})


    def __post_init__(self):
        # Late import to avoid circular dependency
        from jira_offline.config import get_default_user_config_filepath  # pylint: disable=import-outside-toplevel, cyclic-import
        self.user_config_filepath = get_default_user_config_filepath()

        self.display = AppConfig.Display(
            ls_fields = ['issuetype', 'epic_link', 'summary', 'status', 'assignee', 'updated'],
            ls_fields_verbose = ['issuetype', 'epic_link', 'epic_name', 'summary', 'status', 'assignee', 'fix_versions', 'updated'],
            ls_default_filter = 'status not in ("Done", "Story Done", "Epic Done", "Closed")'
        )
        self.sync = AppConfig.Sync()
        self.customfields = dict()


    def write_to_disk(self):
        # Ensure config path exists
        pathlib.Path(click.get_app_dir(__title__)).mkdir(parents=True, exist_ok=True)

        # Late import to avoid circular dependency
        from jira_offline.config import get_app_config_filepath  # pylint: disable=import-outside-toplevel, cyclic-import
        with open(get_app_config_filepath(), 'w') as f:
            json.dump(self.serialize(), f)
            f.write('\n')

    def iter_customfields(self) -> set:
        '''
        Return unique set of customfields defined across all Jiras.
        Hard-coded items are the mandatory customfields specified by Jira server.
        '''
        return {'epic_link', 'epic_name', 'sprint'}.union(*self.customfields.values())


@dataclass
class Issue(DataclassSerializer):
    project_id: str = field(metadata={'friendly': 'Project ID', 'readonly': True})
    issuetype: str = field(metadata={'friendly': 'Type', 'readonly': True})
    project: ProjectMeta = field(repr=False, metadata={'serialize': False})
    summary: str
    key: str = field(metadata={'readonly': True})

    # Core fields
    assignee: Optional[str] = field(default=None)
    created: Optional[datetime.datetime] = field(default=None, metadata={'readonly': True})
    creator: Optional[str] = field(default=None, metadata={'readonly': True})
    description: Optional[str] = field(default=None)
    fix_versions: Optional[set] = field(default_factory=set, metadata={'friendly': 'Fix Version'})
    components: Optional[set] = field(default_factory=set)
    id: Optional[int] = field(default=None, metadata={'readonly': True})
    labels: Optional[set] = field(default_factory=set)
    priority: Optional[str] = field(default=None, metadata={'friendly': 'Priority'})
    reporter: Optional[str] = field(default=None)
    status: Optional[str] = field(default=None, metadata={'friendly': 'Status', 'readonly': True})
    updated: Optional[datetime.datetime] = field(default=None, metadata={'readonly': True})

    # Customfields
    # Fields defined here match the CustomFields class, but must be redefined as dataclasses don't
    # work well with multiple inheritance
    epic_link: Optional[str] = field(default=None)
    epic_name: Optional[str] = field(default=None, metadata={'friendly': 'Epic Short Name'})
    sprint: Optional[str] = field(default=None)

    # Story points special-case Customfield using decimal type
    story_points: Optional[decimal.Decimal] = field(default=None)

    # Parent link is used for all parent/child relationships except epic->issue
    parent_link: Optional[str] = field(default=None)

    # Extended Customfields dict to capture arbitrary user-defined Customfields as strings
    extended: Optional[Dict[str, str]] = field(default_factory=dict)  # type: ignore[assignment]

    # The `original` dict which represents serialized Issue last seen on Jira server
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
                raise CannotSetIssueOriginalDirectly

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
            project_id='', project=ProjectMeta(key=''), issuetype='', summary='', key='', description=''
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
                added_value = removed_value = None

                # Determine if a field has been added and/or removed
                if field_name.startswith('extended.') and self.extended:
                    field_name = field_name[9:]
                    if 'extended' in self.original:
                        removed_value = self.original['extended'][field_name]
                    added_value = self.extended[field_name]
                else:
                    removed_value = self.original.get(field_name)
                    added_value = getattr(self, field_name)

                if removed_value:
                    # Render a removed field in red with a minus
                    removed_field = render_field(Issue, field_name, removed_value, title_prefix='-',
                                                 value_prefix=prefix, color='red')

                if added_value:
                    # Render an added field in green with a plus
                    added_field = render_field(Issue, field_name, added_value, title_prefix='+',
                                               value_prefix=prefix, color='green')

                if removed_value and added_value:
                    return (removed_field, added_field)
                elif removed_value:
                    return (removed_field,)
                else:
                    return (added_field,)

            else:
                # Render a single blank char prefix to ensure the unmodified fields line up nicely
                # with the modified fields. Modified fields are printed with a +/- diff prefix char.
                # Char u2800 is used to prevent the tabulate module from stripping the prefix.
                if modified_fields:
                    title_prefix = '\u2800'
                else:
                    title_prefix = ''

                # Handle render of extended customfields
                if field_name.startswith('extended.') and self.extended:
                    value = self.extended[field_name[9:]]
                else:
                    value = getattr(self, field_name)

                return (render_field(Issue, field_name, value, title_prefix=title_prefix,
                                     value_prefix=prefix),)

        if self.issuetype == 'Epic':
            epicdetails = fmt('epic_name')
        else:
            epicdetails = fmt('epic_link')

        def iter_optionals():
            'Iterate the optional attributes of this issue'
            def iter_fields(field_name, customfield_value) -> Generator[Tuple, None, None]:
                # Always display modified fields
                if modified_fields and field_name in modified_fields:
                    for x in fmt(field_name):
                        yield x
                # Else display fields only when set
                elif getattr(self, field_name, None) or customfield_value:
                    for x in fmt(field_name):
                        yield x

            # First return optionals in specific order
            for field_name in ('sprint', 'priority', 'assignee', 'story_points', 'description',
                               'fix_versions', 'labels', 'components'):
                yield from iter_fields(field_name, None)

            # Next return user-defined customfields
            if self.extended:
                for customfield_name, customfield_value in self.extended.items():
                    yield from iter_fields(f'extended.{customfield_name}', customfield_value)

            # Last return authors and dates
            for field_name in ('reporter', 'creator', 'created', 'updated'):
                yield from iter_fields(field_name, None)

        fields = [
            *fmt('summary', prefix=f'[{self.key}] '),
            *fmt('issuetype'),
            *epicdetails,
            *fmt('status'),
        ] + list(iter_optionals())

        return fields


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

        # Convert Issue.story_points from Decimal to str for pandas
        if attrs['story_points']:
            attrs['story_points'] = str(attrs['story_points'])

        # Create Series and fill blanks with pandas-compatible defaults
        series = pd.Series(attrs).fillna(value=get_dataclass_defaults_for_pandas(Issue))

        # Convert all datetimes to UTC, where they are non-null (which is all non-new issues)
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

        # Remove the extended customfield attrs created by `jira._expand_customfields`
        attrs = {k:v for k,v in attrs.items() if not k.startswith('extended.')}

        # Create a mapping of field names to their pandas default
        pandas_null_defaults = get_dataclass_defaults_for_pandas(Issue)

        def convert(key, value):
            'Convert values from their Pandas types to their python dataclass types'
            f = get_field_by_name(Issue, key)
            typ_ = get_base_type(f.type)

            # Special case for Issue.diff_to_original, as it's a list stored as a JSON string
            if key == 'diff_to_original' and value:
                return json.loads(attrs['diff_to_original'])

            # Process the Pandas array types to python primitives
            if typ_ is list:
                value = list(value)
            elif typ_ is set:
                value = set(value)

            # If the value is the default type for Pandas, then return the default for the dataclass field
            if value == pandas_null_defaults.get(key):
                return f.default
            elif typ_ is datetime.datetime:
                value = value.tz_convert(project.timezone).to_pydatetime()
            elif typ_ is decimal.Decimal:
                value = decimal.Decimal(value)

            return value

        attrs = {k:convert(k, v) for k,v in attrs.items()}

        issue = Issue(**attrs)

        if original:
            issue.set_original(json.loads(original))

        return issue


    def __str__(self) -> str:
        '''
        Render issue to friendly string
        '''
        return tabulate(self.render())

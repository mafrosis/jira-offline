import collections.abc
import copy
import dataclasses
from dataclasses import dataclass, field
import datetime
import decimal
import enum
import json
import logging
import os
import urllib3

import pandas as pd

import jira as mod_jira

from tqdm import tqdm


CUSTOM_FIELD_EPIC_LINK = 'customfield_14182'
CUSTOM_FIELD_EPIC_NAME = 'customfield_14183'
CUSTOM_FIELD_ESTIMATE = 'customfield_10002'

logger = logging.getLogger('jira')


# pylint: disable=too-many-instance-attributes
@dataclass
class Issue:
    assignee: str
    created: str
    creator: str
    description: str
    fixVersions: set
    issuetype: str
    key: str
    labels: set
    lastViewed: str
    priority: str
    project: str
    reporter: str
    status: str
    summary: str
    updated: str
    estimate: int = field(default=None)
    epic_ref: str = field(default=None)
    epic_name: str = field(default=None)

    @classmethod
    def deserialize(cls, attrs: dict) -> object:
        """
        Deserialize JIRA API dict to dataclass
        Support decimal, date/datetime, enum & set
        """
        data = copy.deepcopy(attrs)

        for f in dataclasses.fields(cls):
            v = attrs.get(f.name)
            if v is None:
                continue

            if dataclasses.is_dataclass(f.type):
                data[f.name] = f.type.deserialize(v)
            elif f.type is decimal.Decimal:
                data[f.name] = decimal.Decimal(v)
            elif issubclass(f.type, enum.Enum):
                # convert string to Enum instance
                data[f.name] = f.type(v)
            elif f.type is datetime.date:
                data[f.name] = datetime.datetime.strptime(v, '%Y-%m-%d').date()
            elif f.type is datetime.datetime:
                data[f.name] = datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%f')
            elif f.type is set:
                data[f.name] = set(v)

        return cls(**data)

    def serialize(self) -> dict:
        """
        Serialize dataclass to JIRA API dict
        Support decimal, date/datetime, enum & set
        Include only fields with repr=True (dataclass.field default)
        """
        data = {}

        for f in dataclasses.fields(self):
            if f.repr is False:
                continue

            v = self.__dict__.get(f.name)

            if v is None:
                data[f.name] = None
            elif dataclasses.is_dataclass(f.type):
                data[f.name] = v.serialize()
            elif isinstance(v, decimal.Decimal):
                data[f.name] = str(v)
            elif issubclass(f.type, enum.Enum):
                # convert Enum to raw string
                data[f.name] = v.value
            elif isinstance(v, (datetime.date, datetime.datetime)):
                data[f.name] = v.isoformat()
            elif isinstance(v, set):
                data[f.name] = list(v)
            else:
                data[f.name] = v

        return data


class Jira(collections.abc.MutableMapping):
    _jira = None
    config = None

    def __init__(self, *args, **kwargs):
        self.store = dict()
        self.update(dict(*args, **kwargs))

    def __getitem__(self, key):
        return self.store[self.__keytransform__(key)]

    def __setitem__(self, key, value):
        self.store[self.__keytransform__(key)] = value

    def __delitem__(self, key):
        del self.store[self.__keytransform__(key)]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __keytransform__(self, key):  # pylint: disable=no-self-use
        return key

    def _connect(self, config=None):
        if config is None and self.config is None:
            raise Exception('Jira object not configured')

        if self._jira and self.config:
            return self._jira

        # no insecure cert warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # cache config object
        if config:
            self.config = config

        self._jira = mod_jira.JIRA(
            options={'server': 'https://{}'.format(self.config.hostname), 'verify': False},
            basic_auth=(self.config.username, self.config.password),
        )
        return self._jira

    def pull_issues(self):
        self._connect()

        # load existing issue data from cache
        self.load_issues()

        page = 0

        # single quick query to get total number of issues
        head = self._jira.search_issues(f'project=CNPS', maxResults=1)

        with tqdm(total=head.total, unit=' issues') as pbar:
            while True:
                start = page * 20
                issues = self._jira.search_issues(f'project=CNPS', start, 20)
                if len(issues) == 0:
                    break
                page += 1

                # add/update all issues into self
                for issue in issues:
                    self[issue.key] = self._raw_issue_to_object(issue)

                # update progress
                pbar.update(len(issues))

        logger.info('Retrieved %s issues', pbar.total)

        # dump issues to JSON cache
        json.dump(
            {k:v.serialize() for k,v in self.items()},
            open('issue_cache.json', 'w')
        )
        return self

    def _raw_issue_to_object(self, issue):  # pylint: disable=no-self-use
        """
        Convert raw JSON from JIRA API to a dataclass object
        """
        fixVersions = set()
        if issue.fields.fixVersions:
            fixVersions = {f.name for f in issue.fields.fixVersions}

        return Issue.deserialize({
            'assignee': issue.fields.assignee.name if issue.fields.assignee else None,
            'created': issue.fields.created,
            'creator': issue.fields.creator.name,
            'epic_ref': getattr(issue.fields, CUSTOM_FIELD_EPIC_LINK),
            'epic_name': getattr(issue.fields, CUSTOM_FIELD_EPIC_NAME, ''),
            'estimate': getattr(issue.fields, CUSTOM_FIELD_ESTIMATE),
            'description': issue.fields.description,
            'fixVersions': fixVersions,
            'issuetype': issue.fields.issuetype.name,
            'key': issue.key,
            'labels': issue.fields.labels,
            'lastViewed': issue.fields.lastViewed,
            'priority': issue.fields.priority.name,
            'project': issue.fields.project.key,
            'reporter': issue.fields.reporter.name,
            'status': issue.fields.status.name,
            'summary': issue.fields.summary,
            'updated': issue.fields.updated,
        })

    def load_issues(self) -> pd.DataFrame:
        """
        Load issues from JSON cache file, and store as class variable
        return DataFrame of entire dataset
        """
        if not os.path.exists('issue_cache.json'):
            # first run; cache file doesn't exist
            self.pull_issues()
        else:
            # load from cache file
            for k,v in json.load(open('issue_cache.json')).items():
                self.__setitem__(k, Issue.deserialize(v))

        return self.to_frame()

    def to_frame(self) -> pd.DataFrame:
        """
        Convert self (aka a dict) into pandas DataFrame
        """
        df = pd.DataFrame.from_dict({k:v.__dict__ for k,v in self.items()}, orient='index')
        df = df[ (df.issuetype != 'Delivery Risk') & (df.issuetype != 'Ops/Introduced Risk') ]
        return df

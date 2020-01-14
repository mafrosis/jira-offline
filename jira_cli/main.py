import collections.abc
import json
import logging
import os
import urllib3

import jira as mod_jira
import pandas as pd

from jira_cli.models import Issue
from jira_cli.sync import pull_issues


logger = logging.getLogger('jira')



class Jira(collections.abc.MutableMapping):
    _jira = None
    _df = None
    config = None

    def __init__(self, *args, **kwargs):
        self.store = dict()
        self.update(dict(*args, **kwargs))

    def __getitem__(self, key):
        return self.store[key]

    def __setitem__(self, key, value):
        self.store[key] = value

    def __delitem__(self, key):
        del self.store[key]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def connect(self, config=None):
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

    def load_issues(self) -> None:
        '''
        Load issues from JSON cache file, and store as class variable
        return DataFrame of entire dataset
        '''
        if not os.path.exists('issue_cache.json'):
            # first run; cache file doesn't exist
            pull_issues(self, force=True)
        else:
            # load from cache file
            for k,v in json.load(open('issue_cache.json')).items():
                self[k] = Issue.deserialize(v)

    def write_issues(self):
        '''
        Dump issues to JSON cache file
        '''
        try:
            issues_json = json.dumps({k:v.serialize() for k,v in self.items()})
        except TypeError:
            logger.exception('Cannot write issues cache! Please report this bug..')
            return

        with open('issue_cache.json', 'w') as f:
            f.write(issues_json)

    def invalidate_df(self):
        '''Invalidate internal dataframe, so it's recreated on next access'''
        self._df = None

    @property
    def df(self) -> pd.DataFrame:
        '''
        Convert self (aka a dict) into pandas DataFrame

        - Drop original, diff_to_original fields
        - Drop any issue with issuetype of Risk
        - Include issue.status as a string
        - Include issue.is_open flag
        '''
        if self._df is None:
            items = {}
            for key, issue in self.items():
                if issue.issuetype not in ('Delivery Risk', 'Ops/Introduced Risk'):
                    items[key] = {
                        k:v for k,v in issue.__dict__.items()
                        if k not in ('original', 'diff_to_original')
                    }
                    # convert IssueStatus enum to string
                    items[key]['status'] = issue.status.value
                    items[key]['is_open'] = issue.is_open
            self._df = pd.DataFrame.from_dict(items, orient='index')
        return self._df

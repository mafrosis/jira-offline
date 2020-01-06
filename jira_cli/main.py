import collections.abc
import datetime
import json
import logging
import os
import urllib3

import pandas as pd

import jira as mod_jira

from tabulate import tabulate
from tqdm import tqdm

from jira_cli.models import Issue


CUSTOM_FIELD_EPIC_LINK = 'customfield_14182'
CUSTOM_FIELD_EPIC_NAME = 'customfield_14183'
CUSTOM_FIELD_ESTIMATE = 'customfield_10002'


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

    def pull_issues(self, force=False, verbose=False):
        self._connect()

        if not self.config.projects:
            raise Exception('No projects configured, cannot continue')

        if force or self.config.last_updated is None:
            # first/forced load; cache must be empty
            last_updated = '2010-01-01 00:00'
            logger.info('Querying for all Jira issues')
        else:
            # load existing issue data from cache
            self.load_issues()
            last_updated = self.config.last_updated
            logger.info('Querying for Jira issues since %s', last_updated)

        jql = f'project IN ({",".join(self.config.projects)}) AND updated > "{last_updated}"'

        # single quick query to get total number of issues
        head = self._jira.search_issues(jql, maxResults=1)

        pbar = None

        def _run(jql, pbar=None):
            page = 0
            total = 0

            while True:
                start = page * 25
                issues = self._jira.search_issues(jql, start, 25)
                if len(issues) == 0:
                    break
                page += 1
                total += len(issues)

                # add/update all issues into self
                for issue in issues:
                    self[issue.key] = self._raw_issue_to_object(issue)

                if pbar:
                    # update progress
                    pbar.update(len(issues))
                else:
                    logger.info('Page number %s', page)
                    df = pd.DataFrame.from_dict(
                        {issue.key:self._raw_issue_to_object(issue).serialize() for issue in issues},
                        orient='index'
                    )
                    df['summary'] = df.loc[:]['summary'].str.slice(0, 100)
                    print(tabulate(df[['issuetype', 'summary', 'assignee', 'updated']], headers='keys', tablefmt='psql'))

            return total

        if verbose:
            total = _run(jql)
        else:
            # show progress bar
            with tqdm(total=head.total, unit=' issues') as pbar:
                total = _run(jql, pbar)

        logger.info('Retrieved %s issues', total)

        # dump issues to JSON cache
        self.write_issues()

        # cache the last_updated value
        self.config.last_updated = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        self.config.write_to_disk()

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

    def load_issues(self) -> None:
        """
        Load issues from JSON cache file, and store as class variable
        return DataFrame of entire dataset
        """
        if not os.path.exists('issue_cache.json'):
            # first run; cache file doesn't exist
            self.pull_issues(force=True)
        else:
            # load from cache file
            for k,v in json.load(open('issue_cache.json')).items():
                self[k] = Issue.deserialize(v)

    def write_issues(self):
        """
        Dump issues to JSON cache file
        """
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

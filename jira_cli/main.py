'''
The Jira class in this module is the primary abstraction around the Jira API.
'''
import collections.abc
import json
import logging
import os
from typing import Optional
import urllib3

import jira as mod_jira
from jira.resources import Issue as ApiIssue
import jsonlines
import pandas as pd

from jira_cli.exceptions import (EpicNotFound, EstimateFieldUnavailable, JiraNotConfigured,
                                 MissingFieldsForNewIssue, JiraApiError)
from jira_cli.models import AppConfig, CustomFields, Issue, ProjectMeta
from jira_cli.sync import jiraapi_object_to_issue, pull_issues


logger = logging.getLogger('jira')


class Jira(collections.abc.MutableMapping):
    _jira: mod_jira.JIRA = None
    _df: Optional[pd.DataFrame] = None
    config: AppConfig

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
            options={'server': f'{self.config.protocol}://{self.config.hostname}', 'verify': False},
            basic_auth=(self.config.username, self.config.password),
        )
        return self._jira


    def load_issues(self) -> None:
        '''
        Load issues from JSON cache file, and store in self (as class implements dict interface)
        '''
        if not os.path.exists('issue_cache.jsonl') or os.stat('issue_cache.jsonl').st_size == 0:
            # first run; cache file doesn't exist
            pull_issues(self, force=True)
        else:
            try:
                # load from cache file
                with open('issue_cache.jsonl') as f:
                    for obj in jsonlines.Reader(f.readlines()).iter(type=dict):
                        self[obj['key']] = Issue.deserialize(obj)

            except (KeyError, TypeError, jsonlines.Error):
                logger.exception('Cannot read issues cache! Please report this bug.')
                return


    def write_issues(self):
        '''
        Dump issues to JSON cache file
        '''
        try:
            issues_json = []
            for issue in self.values():
                data = issue.serialize()

                # calculate the diff to the original Issue on Jira for existing Issues
                if issue.exists:
                    data['diff_to_original'] = issue.diff(data)

                issues_json.append(data)
        except TypeError:
            # an error here means the DataclassSerializer output is incompatible with JSON
            logger.exception('Cannot write issues cache! Please report this bug.')
            return

        with open('issue_cache.jsonl', 'w') as f:
            writer = jsonlines.Writer(f)
            writer.write_all(issues_json)


    def get_project_meta(self, project_key: str) -> ProjectMeta:
        '''
        Load additional Jira project meta data from Jira's createmeta API

        Params:
            project_key:  Project key to load metadata for
        Returns:
            Project meta as a dict
        '''
        try:
            api = self.connect()
            data: dict = api.createmeta(project_key)
            return ProjectMeta(
                name=data['projects'][0]['name'],
                issuetypes={x['name'] for x in data['projects'][0]['issuetypes']},
                custom_fields=CustomFields(),
            )

        except (IndexError, KeyError) as e:
            raise JiraApiError(f'Missing or bad project meta returned for {project_key} with error "{e}"')
        except mod_jira.JIRAError as e:
            raise JiraApiError(f'Failed retrieving project meta for {project_key} with error "{e}"')


    def new_issue(self, fields: dict) -> Issue:
        '''
        Create a new issue on a Jira project via the API

        Params:
            fields:  JSON-compatible key-value pairs to create as new Issue
        Returns:
            The new Issue, including the Jira-generated key field
        '''
        if 'key' not in fields or 'issuetype' not in fields or 'summary' not in fields or 'status' not in fields:
            raise MissingFieldsForNewIssue

        try:
            # create a new Issue and store in self
            api = self.connect()

            # key/status are set by Jira server; remove them
            temp_key = fields['key']
            del fields['key']
            del fields['status']

            # create new issue in Jira and update self
            issue: ApiIssue = api.create_issue(fields=fields)

        except mod_jira.JIRAError as e:
            err: str = 'Failed creating new {} "{}" with error "{}"'.format(
                fields['issuetype']['name'],
                fields['summary'],
                e.text
            )
            if e.text == 'gh.epic.error.not.found':
                raise EpicNotFound(err)
            if "Field 'estimate' cannot be set" in e.text:
                raise EstimateFieldUnavailable(err)
            if 'cannot be set. It is not on the appropriate screen, or unknown.' in e.text:
                raise JiraNotConfigured(err)

        # transform the API response and add to self
        new_issue: Issue = jiraapi_object_to_issue(self.config, issue)
        self[new_issue.key] = new_issue  # pylint: disable=no-member

        # remove the placeholder Issue
        del self[temp_key]

        # write changes to disk
        self.write_issues()

        return new_issue


    def update_issue(self, issue: Issue, fields: dict) -> Optional[Issue]:
        '''
        Update an issue on Jira via the API

        WARNING: Uses a private API on the `pycontribs/jira` project.
                 This was done to greatly simplify our interaction with the Jira API; the default
                 API provided by the jira library does many clever things that are not useful for
                 this application.

        Params:
            key:     Jira Issue key
            fields:  JSON-compatible key-value pairs to update
        '''
        try:
            api = self.connect()
            logger.debug('PUT %s/rest/api/2/issue/%s %s', api._options['server'], issue.key, json.dumps(fields)) # pylint: disable=protected-access
            resp = api._session.put( # pylint: disable=protected-access
                f'{api._options["server"]}/rest/api/2/issue/{issue.key}/', # pylint: disable=protected-access
                data=json.dumps({'fields': fields})
            )
            logger.debug(resp)

            if bool(resp.status_code > 200 and resp.status_code < 300):
                # Jira is now updated to match local; synchronize our local reference to the Jira object
                issue.original = issue.serialize()
                self[issue.key] = issue
                return issue

        except mod_jira.JIRAError as e:
            logger.error('Failed updating %s with error "%s"', issue.key, e)

        return None


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

'''
The Jira class in this module is the primary abstraction around the Jira API.
'''
import collections.abc
import json
import logging
import os
from typing import Dict, Optional
import urllib3

import jira as mod_jira
from jira.resources import Issue as ApiIssue
import jsonlines
import pandas as pd

from jira_cli.config import get_cache_filepath, load_config
from jira_cli.exceptions import (EpicNotFound, EstimateFieldUnavailable, JiraApiError,
                                 JiraNotConfigured, MissingFieldsForNewIssue, NoAuthenticationMethod,
                                 ProjectDoesntExist)
from jira_cli.models import AppConfig, CustomFields, Issue, IssueType, ProjectMeta
from jira_cli.sync import jiraapi_object_to_issue


logger = logging.getLogger('jira')


class Jira(collections.abc.MutableMapping):
    _connections: Optional[Dict[str, mod_jira.JIRA]] = None
    _df: Optional[pd.DataFrame] = None

    def __init__(self, *args, **kwargs):
        self.store = dict()
        self.update(dict(*args, **kwargs))

        # load application config without prompting
        self.config: AppConfig = load_config()

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


    def connect(self, project: ProjectMeta):
        '''
        Connect to Jira API and cache the mod_jira.JIRA object each host

        Params:
            project:  Properties of the Jira project to connect to
        '''
        # no insecure cert warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if not self._connections:
            self._connections = {}

        # return pre-cached connection
        if project.id in self._connections:
            return self._connections[project.id]

        basic_auth = oauth = None

        if project.username:
            basic_auth = (project.username, project.password)
        elif project.oauth:
            oauth = project.oauth.serialize()
        else:
            raise NoAuthenticationMethod

        self._connections[project.id] = mod_jira.JIRA(
            options={'server': project.jira_server, 'verify': False},
            basic_auth=basic_auth,
            oauth=oauth,
        )
        return self._connections[project.id]


    def load_issues(self) -> None:
        '''
        Load issues from JSON cache file, and store in self (as class implements dict interface)
        '''
        cache_filepath = get_cache_filepath()
        if os.path.exists(cache_filepath) and os.stat(cache_filepath).st_size > 0:
            try:
                with open(cache_filepath) as f:
                    for obj in jsonlines.Reader(f.readlines()).iter(type=dict):
                        self[obj['key']] = Issue.deserialize(
                            obj, project_ref=self.config.projects[obj['project_id']]
                        )

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

        with open(get_cache_filepath(), 'w') as f:
            writer = jsonlines.Writer(f)
            writer.write_all(issues_json)


    def get_project_meta(self, project: ProjectMeta):
        '''
        Load additional Jira project meta data from Jira's createmeta API

        Params:
            project:  Jira project object into which we should load additional metadata
        '''
        try:
            api = self.connect(project)
            data: dict = api.createmeta(project.key, expand='projects.issuetypes.fields')

            if not data.get('projects'):
                raise ProjectDoesntExist(project.key)

            # project friendly name
            project.name = data['projects'][0]['name']

            # extract set of issuetypes, and their priority values returned from the createmeta API
            for x in data['projects'][0]['issuetypes']:
                it = IssueType(name=x['name'])
                it.priorities = {y['name'] for y in x['fields']['priority']['allowedValues'] }
                project.issuetypes[x['name']] = it

            custom_fields = CustomFields()

            # extract custom fields from the API
            for issuetype in data['projects'][0]['issuetypes']:
                if custom_fields:
                    # exit loop when all custom field mappings have been extracted
                    break

                for field_props in issuetype['fields'].values():
                    if not custom_fields.epic_name and field_props['name'] == 'Epic Name':
                        custom_fields.epic_name = str(field_props['schema']['customId'])
                    elif not custom_fields.epic_ref and field_props['name'] == 'Epic Link':
                        custom_fields.epic_ref = str(field_props['schema']['customId'])
                    elif not custom_fields.estimate and field_props['name'] == 'Story Points':
                        custom_fields.estimate = str(field_props['schema']['customId'])

            if not custom_fields.estimate:
                raise EstimateFieldUnavailable(project.key, project.jira_server)

            project.custom_fields = custom_fields

        except (IndexError, KeyError) as e:
            raise JiraApiError(f'Missing or bad project meta returned for {project.key} with error "{e}"')
        except mod_jira.JIRAError as e:
            raise JiraApiError(f'Failed retrieving project meta for {project.key} with error "{e}"')


    def new_issue(self, project: ProjectMeta, fields: dict) -> Issue:
        '''
        Create a new issue on a Jira project via the API

        Params:
            project:  Properties of the Jira project on which to create new Issue
            fields:   JSON-compatible key-value pairs for new Issue
        Returns:
            The new Issue, including the Jira-generated key field
        '''
        if 'key' not in fields or 'issuetype' not in fields or \
           'summary' not in fields or 'status' not in fields:
            raise MissingFieldsForNewIssue

        try:
            # create a new Issue and store in self
            api = self.connect(project)

            # key/status are set by Jira server; remove them
            temp_key = fields['key']
            del fields['key']
            del fields['status']
            # Jira doesn't know project_id, it's created by this application; remove it
            del fields['project_id']

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
                raise EstimateFieldUnavailable(project.key, project.jira_server)
            if 'cannot be set. It is not on the appropriate screen, or unknown.' in e.text:
                raise JiraNotConfigured(project.key, project.jira_server, err)

        # transform the API response and add to self
        new_issue: Issue = jiraapi_object_to_issue(project, issue)
        self[new_issue.key] = new_issue  # pylint: disable=no-member

        if new_issue.issuetype == 'Epic':  # pylint: disable=no-member
            # relink any issue linked to this epic to the new Jira-generated key
            for linked_issue in [i for i in self.values() if i.epic_ref == temp_key]:
                linked_issue.epic_ref = new_issue.key  # pylint: disable=no-member

        # remove the placeholder Issue
        del self[temp_key]

        # write changes to disk
        self.write_issues()

        return new_issue


    def update_issue(self, project: ProjectMeta, issue: Issue, fields: dict) -> Optional[Issue]:
        '''
        Update an issue on Jira via the API

        WARNING: Uses a private API on the `pycontribs/jira` project.
                 This was done to greatly simplify our interaction with the Jira API; the default
                 API provided by the jira library does many clever things that are not useful for
                 this application.

        Params:
            project:  Properties of the Jira project to update
            issue:    Issue object to update
            fields:   JSON-compatible key-value pairs to write
        '''
        try:
            api = self.connect(project)
            logger.debug('PUT %s/rest/api/2/issue/%s %s', project.jira_server, issue.key, json.dumps(fields))
            resp = api._session.put( # pylint: disable=protected-access
                f'{project.jira_server}/rest/api/2/issue/{issue.key}/',
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

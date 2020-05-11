'''
The Jira class in this module is the primary abstraction around the Jira API.
'''
import collections.abc
import logging
import os
from typing import Optional

import jsonlines
import pandas as pd

from jira_offline.config import get_cache_filepath, load_config
from jira_offline.exceptions import (EpicNotFound, EstimateFieldUnavailable, JiraApiError,
                                     JiraNotConfigured, MissingFieldsForNewIssue, ProjectDoesntExist)
from jira_offline.models import AppConfig, CustomFields, Issue, IssueType, ProjectMeta
from jira_offline.utils.api import get as api_get, post as api_post, put as api_put
from jira_offline.utils.convert import jiraapi_object_to_issue


logger = logging.getLogger('jira')


class Jira(collections.abc.MutableMapping):
    _connections = None
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


    def get_project_meta(self, project: ProjectMeta):  # pylint: disable=no-self-use
        '''
        Load additional Jira project meta data from Jira's createmeta API

        Params:
            project:  Jira project object into which we should load additional metadata
        '''
        try:
            params = {'projectKeys': project.key, 'expand': 'projects.issuetypes.fields'}
            data = api_get(project, 'issue/createmeta', params=params)
            if not data.get('projects'):
                raise ProjectDoesntExist(project.key)

            # project friendly name
            project.name = data['projects'][0]['name']

            issuetypes_ = dict()

            # extract set of issuetypes, and their priority values returned from the createmeta API
            for x in data['projects'][0]['issuetypes']:
                it = IssueType(name=x['name'])
                if x['fields'].get('priority'):
                    it.priorities = {y['name'] for y in x['fields']['priority']['allowedValues']}
                issuetypes_[x['name']] = it

            # update project issuetypes to latest defined on Jira
            project.issuetypes = issuetypes_

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

            project.custom_fields = custom_fields

            # pull project statuses for issue types
            self._get_project_issue_statuses(project)

        except (IndexError, KeyError) as e:
            raise JiraApiError(f'Missing or bad project meta returned for {project.key} with error "{e.__class__.__name__}({e})"')
        except JiraApiError as e:
            raise JiraApiError(f'Failed retrieving project meta for {project.key} with error "{e}"')


    def _get_project_issue_statuses(self, project: ProjectMeta):  # pylint: disable=no-self-use
        '''
        Pull valid statuses for each issuetype in this project

        Params:
            project:  Jira project to query
        '''
        try:
            data = api_get(project, f'project/{project.key}/statuses')

            for obj in data:
                try:
                    issuetype = project.issuetypes[obj['name']]
                    issuetype.statuses = {x['name'] for x in obj['statuses']}
                except KeyError:
                    logger.debug('Unknown issuetype "%s" returned from /project/{project.key}/statuses', obj['name'])

        except JiraApiError as e:
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
        if 'key' not in fields or 'issuetype' not in fields or 'summary' not in fields:
            raise MissingFieldsForNewIssue(
                '{} is missing a mandatory field {}'.format(fields['key'], ','.join(fields))
            )

        try:
            # key/status are set by Jira server; remove them
            temp_key = fields['key']
            del fields['key']
            # Jira doesn't know project_id, it's created by this application; remove it
            del fields['project_id']

            # create new issue in Jira
            data = api_post(project, 'issue', data={'fields': fields})

            # retrieve the freshly minted Jira issue
            new_issue: Issue = self.fetch_issue(project, data['key'])

        except JiraApiError as e:
            err: str = 'Failed creating new {} "{}" with error "{}"'.format(
                fields['issuetype']['name'],
                fields['summary'],
                e.inner_message
            )
            if e.inner_message == 'gh.epic.error.not.found':
                raise EpicNotFound(err)
            if "Field 'estimate' cannot be set" in e.inner_message:
                raise EstimateFieldUnavailable(project.key, project.jira_server)
            if 'cannot be set. It is not on the appropriate screen, or unknown.' in e.inner_message:
                raise JiraNotConfigured(project.key, project.jira_server, err)

        # add to self under the new key
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

        Params:
            project:  Properties of the Jira project to update
            issue:    Issue object to update
            fields:   JSON-compatible key-value pairs to write
        '''
        try:
            api_put(project, f'issue/{issue.key}', data={'fields': fields})

            # Jira is now updated to match local; synchronize our local reference to the Jira object
            issue.original = issue.serialize()
            self[issue.key] = issue
            return issue

        except JiraApiError as e:
            logger.error('Failed updating %s with error "%s"', issue.key, e)

        return None


    def fetch_issue(self, project: ProjectMeta, key: str) -> Issue:  # pylint: disable=no-self-use
        '''
        Return a single Issue object from the Jira API by key

        Params:
            project:  Properties of the project pushing issues to
            key:      Issue key to lookup on Jira API
        Returns:
            Issue dataclass instance
        '''
        data = api_get(project, f'issue/{key}')
        return jiraapi_object_to_issue(project, data)


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
                items[key] = {
                    k:v for k,v in issue.__dict__.items()
                    if k not in ('original', 'diff_to_original')
                }
            self._df = pd.DataFrame.from_dict(items, orient='index')
            # rename the columns sourced from @property on Issue
            self._df.rename(columns={'_status': 'status', '_priority': 'priority'}, inplace=True)
        return self._df

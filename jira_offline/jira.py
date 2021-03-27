'''
The Jira class in this module is the primary abstraction around the Jira API.
'''
import collections.abc
import dataclasses
import json
import logging
import os
from typing import Dict, List, Optional, Set

import pandas as pd
from peak.util.proxies import LazyProxy

from jira_offline.config import get_cache_filepath, load_config
from jira_offline.exceptions import (EpicNotFound, EstimateFieldUnavailable, JiraApiError,
                                     JiraNotConfigured, MissingFieldsForNewIssue,
                                     MultipleTimezoneError, ProjectDoesntExist)
from jira_offline.models import AppConfig, CustomFields, IssueFilter, Issue, IssueType, ProjectMeta
from jira_offline.utils.api import get as api_get, post as api_post, put as api_put
from jira_offline.utils.convert import jiraapi_object_to_issue
from jira_offline.utils.decorators import auth_retry


logger = logging.getLogger('jira')


# Create single Jira object instance for this invocation of the app
# Made available to all modules via simply python import: `from jira_offline.utils import jira`
jira = LazyProxy(lambda: Jira())  # pylint: disable=unnecessary-lambda


class Jira(collections.abc.MutableMapping):
    _df: pd.DataFrame

    filter: IssueFilter


    def __init__(self):
        self.store = dict()

        # Create the underlying storage for persisting Issues
        self._df = pd.DataFrame()

        # load application config without prompting
        self.config: AppConfig = load_config()

        # Initialise an empty filter
        self.filter = IssueFilter(self)


    def __getitem__(self, key: str) -> Issue:
        series = self._df.loc[key]
        return Issue.from_series(
            series,
            project=self.config.projects[series['project_id']]
        )

    def __setitem__(self, key: str, issue: Issue):
        series = issue.to_series()
        self._df.loc[key] = series

    def __delitem__(self, key: str):
        self._df.drop(key, inplace=True)

    def __iter__(self):
        return (k for k, row in self._df.iterrows())

    def __len__(self):
        return len(self._df)

    def __contains__(self, key):
        return key in self._df.index


    @property
    def df(self) -> pd.DataFrame:
        return self.filter.apply()


    def update(self, issues: List[Issue]):  # type: ignore[override] # pylint: disable=arguments-differ
        '''
        Merge another DataFrame of Issues to the store. New issues are appended to the underlying
        DataFrame and existing modified issues are updated in-place.

        This method is called during sync with Jira server.

        Notably this method _does not_ use the logic in Issue.to_series() for performance reasons;
        it's much faster to build the DataFrame and operate on that, than to process each Issue in a
        tight loop and then create a DataFrame.
        '''
        # Validate all timezones are the same for this DataFrame, as the following tz_convert() call
        # fails when they differ.
        # It's not possible for a single Jira to return issues with multiple different timezones.
        if not all(i.created.tzinfo == issues[0].created.tzinfo for i in issues):  # type: ignore[union-attr]
            raise MultipleTimezoneError
        if not all(i.updated.tzinfo == issues[0].updated.tzinfo for i in issues):  # type: ignore[union-attr]
            raise MultipleTimezoneError

        # Construct a DataFrame from the passed list of Issues
        # also fill any NaNs with blank
        df = pd.DataFrame.from_dict(
            {issue.key:issue.__dict__ for issue in issues},
            orient='index'
        ).fillna('')

        # Convert all datetimes to UTC
        for col in ('created', 'updated'):
            df[col] = df[col].dt.tz_convert('UTC')

        # PyArrow does not like decimals
        df['estimate'] = df['estimate'].astype('string')

        # Convert the "project" object column - which contains ProjectMeta instances -
        # into "project_key" - a string column
        df.loc[:, 'project_key'] = [p.key if p else None for p in df['project']]

        # Drop columns for fields marked repr=False
        df.drop(
            columns=[f.name for f in dataclasses.fields(Issue) if f.repr is False],
            inplace=True,
        )

        # Render diff_to_original as a string for storage in the DataFrame
        df['diff_to_original'] = df['diff_to_original'].apply(json.dumps)

        # Add an empty column to for Issue.original
        df['original'] = ''

        # Append any new issues
        self._df = pd.concat([ self._df, df[~df.key.isin(self._df.index)] ])

        # In-place update for modified issues
        self._df.update(df)

        # Let Pandas pick the best datatypes
        self._df = self._df.convert_dtypes()

        # write to disk
        self.write_issues()


    class KeysView(collections.abc.KeysView):
        '''Override KeysView to enable filtering via __iter__'''
        def __init__(self, jira_, filter_):
            self.filter = filter_
            super().__init__(jira_)

        def __iter__(self):
            for key in self.filter.apply().index:
                yield key

    class ItemsView(collections.abc.ItemsView):
        '''Override ItemsView to enable filtering via __iter__'''
        def __init__(self, jira_, filter_):
            self.filter = filter_
            super().__init__(jira_)

        def __iter__(self):
            for key in self.filter.apply().index:
                yield (key, self._mapping[key])

    class ValuesView(collections.abc.ValuesView):
        '''Override ValuesView to enable filtering via __iter__'''
        def __init__(self, jira_, filter_):
            self.filter = filter_
            super().__init__(jira_)

        def __iter__(self):
            for key in self.filter.apply().index:
                yield self._mapping[key]

    def keys(self):
        return Jira.KeysView(self, self.filter)

    def items(self):
        return Jira.ItemsView(self, self.filter)

    def values(self):
        return Jira.ValuesView(self, self.filter)


    def load_issues(self) -> None:
        '''
        Load issues from parquet cache file, and store in underlying pandas DataFrame
        '''
        cache_filepath = get_cache_filepath()
        if os.path.exists(cache_filepath) and os.stat(cache_filepath).st_size > 0:
            self._df = pd.read_parquet(cache_filepath).convert_dtypes()

            # add an empty column to for Issue.original
            self._df['original'] = ''

    def write_issues(self):
        '''
        Dump issues to parquet cache file
        '''
        # Don't write out the original field, as diff_to_original will recreate it
        self._df.drop(columns=['original'], inplace=True)

        # convert `set` columns to `list`, as `set` will not serialize via PyArrow when writing
        # to disk
        for col in ('components', 'fix_versions', 'labels'):
            self._df[col] = self._df[col].apply(list)

        cache_filepath = get_cache_filepath()
        self._df.to_parquet(cache_filepath)


    @auth_retry()
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

            issuetypes_: Dict[str, IssueType] = dict()
            priorities_: Set[str] = set()

            # extract set of issuetypes, and their priority values returned from the createmeta API
            for x in data['projects'][0]['issuetypes']:
                issuetypes_[x['name']] = IssueType(name=x['name'])

                # priority is a project-level setting, which can be extracted from any issue with the
                # "priority" field
                if not priorities_ and x['fields'].get('priority'):
                    priorities_ = {y['name'] for y in x['fields']['priority']['allowedValues']}

            # update project issuetypes & priorities to latest defined on Jira
            project.issuetypes = issuetypes_
            project.priorities = priorities_

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

            # pull project components
            self._get_project_components(project)

        except (IndexError, KeyError) as e:
            raise JiraApiError(f'Missing or bad project meta returned for {project.key} with error "{e.__class__.__name__}({e})"')


    def _get_project_issue_statuses(self, project: ProjectMeta):  # pylint: disable=no-self-use
        '''
        Pull valid statuses for each issuetype in this project

        Params:
            project:  Jira project to query
        '''
        data = api_get(project, f'project/{project.key}/statuses')

        for obj in data:
            try:
                issuetype = project.issuetypes[obj['name']]
                issuetype.statuses = {x['name'] for x in obj['statuses']}
            except KeyError:
                logger.debug('Unknown issuetype "%s" returned from /project/{project.key}/statuses', obj['name'])


    def _get_project_components(self, project: ProjectMeta):  # pylint: disable=no-self-use
        '''
        Pull set of components for this project

        Params:
            project:  Jira project to query
        '''
        data = api_get(project, f'project/{project.key}/components')
        project.components = {x['name'] for x in data}


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
            # key is set by Jira server; remove it
            temp_key = fields['key']
            del fields['key']
            # project_id is application data; remove it
            del fields['project_id']

            # create new issue in Jira
            data = api_post(project, 'issue', data={'fields': fields})

            # retrieve the freshly minted Jira issue
            new_issue: Issue = self.fetch_issue(project, data['key'])

        except JiraApiError as e:
            err: str = 'Failed creating new {} "{}" with error "{}"'.format(
                fields['issuetype']['name'],
                fields['summary'],
                e.message
            )
            if e.message == 'gh.epic.error.not.found':
                raise EpicNotFound(err)
            if "Field 'estimate' cannot be set" in e.message:
                raise EstimateFieldUnavailable(project.key, project.jira_server)
            if 'cannot be set. It is not on the appropriate screen, or unknown.' in e.message:
                raise JiraNotConfigured(project.key, project.jira_server, err)

        if new_issue.key is None:
            # This code path is not reachable, as the `key` field is mandatory on the Jira API. This
            # is included to keep the type-checker happy
            raise Exception

        # add to self under the new key
        self[new_issue.key] = new_issue

        if new_issue.issuetype == 'Epic':
            # relink any issue linked to this epic to the new Jira-generated key
            for linked_issue in [i for i in self.values() if i.epic_ref == temp_key]:
                linked_issue.epic_ref = new_issue.key

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

            if issue.key is None:
                # this code path is not possible, as Jira always provides the key field
                # but it keeps the type-checker happy
                raise Exception

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

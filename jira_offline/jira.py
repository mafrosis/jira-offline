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
import pytz

from jira_offline.config import get_cache_filepath, load_config
from jira_offline.exceptions import JiraApiError, MultipleTimezoneError, ProjectDoesntExist
from jira_offline.models import AppConfig, CustomFields, Issue, IssueType, ProjectMeta
from jira_offline.sql_filter import IssueFilter
from jira_offline.utils.api import get as api_get, post as api_post, put as api_put
from jira_offline.utils.convert import jiraapi_object_to_issue
from jira_offline.utils.decorators import auth_retry


logger = logging.getLogger('jira')


# Create single Jira object instance for this invocation of the app
# Made available to all modules via simple python import: `from jira_offline.jira import jira`
jira = LazyProxy(lambda: Jira())  # pylint: disable=unnecessary-lambda


class Jira(collections.abc.MutableMapping):
    _df: pd.DataFrame

    filter: IssueFilter


    def __init__(self):
        self.store = dict()

        # Create the underlying storage for persisting Issues
        self._df = pd.DataFrame()

        # Load application config without prompting
        self.config: AppConfig = load_config()

        # Initialise an empty filter
        self.filter = IssueFilter()


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

        # Construct a DataFrame from the passed list of Issues, and fill any NaNs with blank
        df = pd.DataFrame.from_dict(
            {issue.key:issue.__dict__ for issue in issues},
            orient='index'
        ).fillna('')

        # Convert all datetimes to UTC
        for col in ('created', 'updated'):
            df[col] = df[col].dt.tz_convert('UTC')

        # Extract ProjectMeta.key into a new string column named `project_key`
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

        # Customfields are stored as a dict in the extended column of the DataFrame
        self._df = self._expand_customfields()

        # Let Pandas pick the best datatypes
        self._df = self._df.convert_dtypes()

        # Persist new data to disk
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


    def _expand_customfields(self) -> pd.DataFrame:
        '''
        Customfields are stored as a dict in the extended column of the DataFrame. Expand the
        key-value pairs from the dict into columns.
        '''
        # Drop all extended columns, previously created via this method
        df1 = self._df.drop(self._df.columns[self._df.columns.str.startswith('extended.')], axis=1)

        # Expand extended dict into columns in a new DataFrame
        # Prefix each field with "extended."
        df2 = self._df['extended'].apply(pd.Series).add_prefix('extended.')

        # Merge the customfields columns onto the core DataFrame
        return pd.merge(df1, df2, left_index=True, right_index=True)


    def load_issues(self) -> None:
        '''
        Load issues from feather cache file, and store in underlying pandas DataFrame.
        '''
        if not self._df.empty:
            return

        cache_filepath = get_cache_filepath()
        if os.path.exists(cache_filepath) and os.stat(cache_filepath).st_size > 0:
            self._df = pd.read_feather(
                cache_filepath
            ).set_index('key', drop=False).rename_axis(None).convert_dtypes()

            # Add an empty column to for Issue.original
            self._df['original'] = ''

            # Customfields are stored as a dict in the extended column of the DataFrame
            self._df = self._expand_customfields()

        else:
            # Handle the case where an empty project has been cloned, which results in no Feather
            # file on disk.
            self._df = pd.DataFrame(columns=[
                'project_id', 'issuetype', 'summary', 'key', 'assignee', 'created',
                'creator', 'description', 'fix_versions', 'components', 'id', 'labels',
                'priority', 'reporter', 'status', 'updated', 'epic_link', 'epic_name',
                'sprint', 'story_points', 'extended', 'diff_to_original', 'modified',
                'project_key', 'original', 'parent_link'
            ])


    def write_issues(self):
        '''
        Dump issues to feather cache file.
        '''
        # Make a copy of the DataFrame, for munging before write
        # Don't write out the original field as it can be recreated from Issue.diff_to_original
        df = self._df.drop(columns=['original'])

        # Drop the extended columns, which were created via `self._expand_customfields`
        df.drop(df.columns[df.columns.str.startswith('extended.')], axis=1, inplace=True)

        # PyArrow does not like sets
        for col in ('components', 'fix_versions', 'labels'):
            df[col] = df[col].apply(list)

        # PyArrow does not like decimals
        df['story_points'] = df['story_points'].astype('string')

        cache_filepath = get_cache_filepath()
        df.reset_index(drop=True).to_feather(cache_filepath)


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

            # Project friendly name
            project.name = data['projects'][0]['name']

            # Jira's internal ID for this project
            project.jira_id = data['projects'][0]['id']

            issuetypes_: Dict[str, IssueType] = dict()
            priorities_: Set[str] = set()

            # Extract set of issuetypes, and their priority values returned from the createmeta API
            for x in data['projects'][0]['issuetypes']:
                issuetypes_[x['name']] = IssueType(name=x['name'])

                # Priority is a project-level setting, which can be extracted from any issue with the
                # "priority" field
                if not priorities_ and x['fields'].get('priority'):
                    priorities_ = {y['name'] for y in x['fields']['priority']['allowedValues']}

            # Update project issuetypes & priorities to latest defined on Jira
            project.issuetypes = issuetypes_
            project.priorities = priorities_

            # Map all customfields for this project
            self._load_customfields(project, data['projects'][0]['issuetypes'])

            # Pull project statuses for issue types
            self._get_project_issue_statuses(project)

            # Pull project components
            self._get_project_components(project)

            # Pull user's configured timezone from their profile and store on the ProjectMeta
            tz = self._get_user_timezone(project)
            if tz is not None:
                project.timezone = pytz.timezone(tz)

        except (IndexError, KeyError) as e:
            raise JiraApiError((
                f'Missing or bad project meta returned for {project.key} with error '
                f'"{e.__class__.__name__}({e})"'
            ))


    def _load_customfields(self, project: ProjectMeta, issuetypes_data: dict):
        '''
        Load the customfields for this project from the Jira API.

        User-specified customfields are added to jira-offline.ini and can be accessed via
        `jira.config.customfields`. Projects can have 0-N configured customfields, this method
        does the mapping between the two.

        Params:
            project:          Jira project to query
            issuetypes_data:  Data from Jira API describing issuetypes on this project
        '''
        project_customfields = {}

        # Extract custom fields from the API response for each issuetype on this project
        for issuetype in issuetypes_data:
            for name, field_props in issuetype['fields'].items():
                if name.startswith('customfield_'):
                    project_customfields[name] = field_props

        logger.debug('Customfields for project %s are %s', project.key, project_customfields)

        customfield_epic_name = customfield_epic_link = customfield_sprint = customfield_parent_link = ''

        # Epic Name, Epic Link & Sprint are "locked" custom fields, and so should always exist
        for name, field_props in project_customfields.items():
            if field_props['name'] == 'Epic Name':
                customfield_epic_name = field_props.get('fieldId', field_props.get('key'))
            elif field_props['name'] == 'Epic Link':
                customfield_epic_link = field_props.get('fieldId', field_props.get('key'))
            elif field_props['name'] == 'Sprint':
                customfield_sprint = field_props.get('fieldId', field_props.get('key'))
            elif field_props['name'] == 'Parent Link':
                customfield_parent_link = field_props.get('fieldId', field_props.get('key'))

        # Initialise project's customfields
        project.customfields = CustomFields(
            epic_name=customfield_epic_name,
            epic_link=customfield_epic_link,
            sprint=customfield_sprint,
            parent_link=customfield_parent_link,
        )

        def apply_customfield_config(name, value):
            '''
            Apply user-defined customfield configuration to this Jira project, if mapped in the Jira
            project metadata.

            Customfields must be mapped on the Jira server to this project _and_ be set in the
            user's configuration.
            '''
            # Check to ensure the user-defined customfield is in use on this project
            if value in project_customfields.keys():
                # Replace field name dashes with underscores
                name = name.replace('-', '_')

                if hasattr(project.customfields, name):
                    setattr(project.customfields, name, value)
                else:
                    project.customfields.extended[name] = value

        # Iterate customfields defined in user config
        for jira_host, customfield_mapping in self.config.customfields.items():
            # Only apply config set for this Jira host. Matching is either all Jiras with
            # asterisk, or by Jira server with hostname match
            if jira_host in ('*', project.hostname):
                for name, value in customfield_mapping.items():
                    apply_customfield_config(name, value)


    def _get_user_timezone(self, project: ProjectMeta) -> Optional[str]:  # pylint: disable=no-self-use
        '''
        Retrieve user-specific timezone setting

        Params:
            project:  The project mapped to the Jira to query for timezone info
        '''
        data = api_get(project, 'myself')
        return data.get('timeZone')


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


    def new_issue(self, project: ProjectMeta, fields: dict, offline_temp_key: str) -> Issue:
        '''
        Create a new issue on a Jira project via the API. A POST request is immediately followed by a
        GET for the new issue, to retrive the new key and other default fields provided by the Jira
        server.

        Params:
            project:           Properties of the Jira project on which to create new Issue
            fields:            K/V pairs for the issue; output from `utils.convert.issue_to_jiraapi_update`
            offline_temp_key:  Temporary key created for this issue until it's sync'd to Jira
        Returns:
            The new Issue, including the Jira-generated key field
        '''
        # Create new issue in Jira
        data = api_post(project, 'issue', data={'fields': fields})

        # Retrieve the freshly minted Jira issue
        new_issue: Issue = self.fetch_issue(project, data['key'])

        if new_issue.key is None:
            # This code path is not reachable, as the `key` field is mandatory on the Jira API. This
            # is included to keep the type-checker happy
            raise Exception

        # Add to self under the new key
        self[new_issue.key] = new_issue

        for link_name in ('epic_link', 'parent_link'):
            # Re-link all issues to the new Jira-generated key
            for key in self._df.loc[self._df[link_name] == offline_temp_key, 'key']:
                linked_issue = jira[key]
                setattr(linked_issue, link_name, new_issue.key)
                linked_issue.commit()

        # Remove the placeholder Issue
        del self[offline_temp_key]

        # Write changes to disk
        self.write_issues()

        return new_issue


    def update_issue(self, project: ProjectMeta, issue: Issue, fields: dict):
        '''
        Update an issue on a Jira project via the API. A PUT request is immediately followed by a
        GET for the updated issue - which is rather heavyweight, but ensures that issue timestamps
        are correct as they can only be set by the Jira server.

        Params:
            project:  Properties of the Jira project to update
            issue:    Issue object to update
            fields:   K/V pairs for the issue; output from `utils.convert.issue_to_jiraapi_update`
        '''
        api_put(project, f'issue/{issue.key}', data={'fields': fields})

        # Jira is now updated to match local; synchronise offline issue to the server version
        issue_data = api_get(project, 'issue/EGG-1')
        self[issue.key] = jiraapi_object_to_issue(project, issue_data)

        # Write changes to disk
        self.write_issues()


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

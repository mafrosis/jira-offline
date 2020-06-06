'''
Tests for pull_issues() and pull_single_project() in the sync module
'''
from unittest import mock
import pytest

from fixtures import ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF, ISSUE_2
from jira_offline.exceptions import FailedPullingIssues, JiraApiError
from jira_offline.models import Issue
from jira_offline.sync import IssueUpdate, pull_issues, pull_single_project


@mock.patch('jira_offline.sync.pull_single_project')
def test_pull_issues__does_call_load_issues_when_self_empty(mock_pull_single_project, mock_jira):
    '''
    Ensure pull_issues() calls load_issues() when self (the Jira class dict) is empty
    '''
    pull_issues(mock_jira)
    assert mock_jira.load_issues.called


@mock.patch('jira_offline.sync.pull_single_project')
def test_pull_issues__doesnt_call_load_issues_when_self_populated(mock_pull_single_project, mock_jira):
    '''
    Ensure pull_issues() doesn't call load_issues() when self (the Jira class dict) has issues
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    pull_issues(mock_jira)
    assert not mock_jira.load_issues.called


@mock.patch('jira_offline.sync.pull_single_project')
def test_pull_issues__calls_pull_single_project_for_each_project(mock_pull_single_project, mock_jira, project):
    '''
    Ensure that pull_single_project() is called for each project
    '''
    pull_issues(mock_jira, force=True, verbose=False)
    mock_pull_single_project.assert_called_once_with(mock_jira, project, force=True, verbose=False)


@mock.patch('jira_offline.sync.pull_single_project')
def test_pull_issues__calls_get_project_meta_for_each_project(mock_pull_single_project, mock_jira, project):
    '''
    Ensure that pull_single_project() is called for each project
    '''
    pull_issues(mock_jira, force=True, verbose=False)
    mock_jira.get_project_meta.assert_called_once_with(project)


@mock.patch('jira_offline.sync.pull_single_project')
def test_pull_issues__pulls_only_specified_projects(mock_pull_single_project, mock_jira, project):
    '''
    Ensure that pull_single_project() is called for each project specified in `projects` parameter
    '''
    pull_issues(mock_jira, projects={'TEST'}, force=True, verbose=False)
    mock_pull_single_project.assert_called_once_with(mock_jira, project, force=True, verbose=False)


@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.tqdm')
def test_pull_single_project__last_updated_set_causes_filter_query_from_last_updated(mock_tqdm, mock_api_get, mock_jiraapi_object_to_issue, mock_jira, project):
    '''
    Test config.last_updated being set causes a filtered query from value of last_updated
    '''
    # mock Jira search_issues to return a single result
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    # mock the only project fixture to have a specific last_updated value
    mock_jira.config.projects['99fd9182cfc4c701a8a662f6293f4136201791b4'].last_updated = '2019-01-01 00:00'

    pull_single_project(mock_jira, project, force=False, verbose=False)

    assert mock_api_get.call_args_list[1][1]['params']['jql'] == 'project = TEST AND updated > "2019-01-01 00:00"'


@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.tqdm')
def test_pull_single_project__last_updated_missing_causes_filter_from_waaay_back(mock_tqdm, mock_api_get, mock_jiraapi_object_to_issue, mock_jira, project):
    '''
    Test config.last_updated NOT being set causes a filtered query from 2010-01-01
    '''
    # mock Jira search_issues to return a single result
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    pull_single_project(mock_jira, project, force=False, verbose=False)

    assert mock_api_get.call_args_list[1][1]['params']['jql'] == 'project = TEST AND updated > "2010-01-01 00:00"'


@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.tqdm')
def test_pull_single_project__last_updated_set_AND_force_set_causes_filter_from_waaay_back(mock_tqdm, mock_api_get, mock_jiraapi_object_to_issue, mock_jira, project):
    '''
    Test config.last_updated being set causes a filtered query from value of last_updated
    '''
    # mock Jira search_issues to return a single result
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    # mock the only project fixture to have a specific last_updated value
    mock_jira.config.projects['99fd9182cfc4c701a8a662f6293f4136201791b4'].last_updated = '2019-01-01 00:00'

    pull_single_project(mock_jira, project, force=True, verbose=False)

    assert mock_api_get.call_args_list[1][1]['params']['jql'] == 'project = TEST AND updated > "2010-01-01 00:00"'


@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.tqdm')
def test_pull_single_project__error_handled_when_get_raises_jira_exception(mock_tqdm, mock_api_get, mock_jira, project):
    '''
    Ensure an exception is raised and handled when the get API call raises a Jira exception
    '''
    mock_api_get.side_effect = JiraApiError

    with pytest.raises(FailedPullingIssues):
        pull_single_project(mock_jira, project, force=False, verbose=False)


@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.tqdm')
def test_pull_single_project__write_issues_and_config_called(
        mock_tqdm, mock_api_get, mock_jiraapi_object_to_issue, mock_jira, project
    ):
    '''
    Test write_issues method is called
    Test config.write_to_disk method is called
    '''
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    pull_single_project(mock_jira, project, force=False, verbose=False)
    assert mock_jira.config.write_to_disk.called


@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.tqdm')
def test_pull_single_project__adds_issues_to_self(mock_tqdm, mock_api_get, mock_jiraapi_object_to_issue, mock_jira, project):
    '''
    Ensure that issues returned by search_issues(), are added to the Jira object (which implements dict)
    '''
    # mock Jira API to return two issues
    mock_api_get.side_effect = [ {'total': 2}, {'issues': [ISSUE_1, ISSUE_2]}, {'issues': []} ]

    # mock conversion function to return two Issues
    mock_jiraapi_object_to_issue.side_effect = [Issue.deserialize(ISSUE_1), Issue.deserialize(ISSUE_2)]

    assert len(mock_jira.keys()) == 0
    pull_single_project(mock_jira, project, force=False, verbose=False)
    assert len(mock_jira.keys()) == 2


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.click')
def test_pull_single_project__merge_issues_NOT_called_when_updated_issue_NOT_modified(
        mock_click, mock_api_get, mock_jiraapi_object_to_issue, mock_merge_issues, mock_jira, project
    ):
    '''
    Ensure that merge_issues is NOT called when the Issue does not already exist
    '''
    # mock search_issues to return single Issue
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    # mock conversion function to return single Issue
    mock_jiraapi_object_to_issue.side_effect = [Issue.deserialize(ISSUE_1)]

    pull_single_project(mock_jira, project, force=False, verbose=False)

    # no conflict is found
    assert mock_merge_issues.called is False


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.click')
def test_pull_single_project__merge_issues_called_when_local_issue_is_modified(
        mock_click, mock_api_get, mock_jiraapi_object_to_issue, mock_merge_issues, mock_jira, project
    ):
    '''
    Ensure that merge_issues is called when the Issue already exists
    '''
    # preload the local cache with a modified issue
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock search_issues to return single object
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    # mock conversion function to return single Issue
    mock_jiraapi_object_to_issue.side_effect = [Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)]

    pull_single_project(mock_jira, project, force=False, verbose=False)

    # conflict found; merge called
    assert mock_merge_issues.called is True


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.click')
def test_pull_single_project__merge_issues_NOT_called_when_local_issue_is_modified_BUT_force_is_true(
        mock_click, mock_api_get, mock_jiraapi_object_to_issue, mock_merge_issues, mock_jira, project
    ):
    '''
    Ensure that merge_issues is NOT called the Issue already exists BUT force is called
    '''
    # preload the local cache with a modified issue
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock search_issues to return single object
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    # mock conversion function to return single Issue
    mock_jiraapi_object_to_issue.side_effect = [Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)]

    pull_single_project(mock_jira, project, force=True, verbose=False)

    # conflict found; merge called
    assert mock_merge_issues.called is False


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.jiraapi_object_to_issue')
@mock.patch('jira_offline.sync.api_get')
@mock.patch('jira_offline.sync.click')
def test_pull_single_project__return_from_merge_issues_added_to_self(
        mock_click, mock_api_get, mock_jiraapi_object_to_issue, mock_merge_issues, mock_jira, project
    ):
    '''
    Check that return from merge_issues is added to Jira object (which implements dict)
    '''
    # preload the local cache with a modified issue
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock search_issues to return single object
    mock_api_get.side_effect = [ {'total': 1}, {'issues': [ISSUE_1]}, {'issues': []} ]

    modified_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)

    # mock conversion function to return single Issue
    mock_jiraapi_object_to_issue.side_effect = [modified_issue]

    modified_issue.assignee = 'undertest'

    # mock merge_issues function to return modified_issue
    mock_merge_issues.return_value = IssueUpdate(merged_issue=modified_issue)

    pull_single_project(mock_jira, project, force=False, verbose=False)

    # validate that return from merge_issues is added as TEST-71
    assert mock_jira['TEST-71'].assignee == 'undertest'

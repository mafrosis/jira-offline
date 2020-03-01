from unittest import mock
import pytest

from fixtures import ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF, ISSUE_2
from jira_cli.exceptions import FailedPullingIssues, JiraApiError
from jira_cli.models import Issue
from jira_cli.sync import IssueUpdate, pull_issues


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__calls_connect(mock_tqdm, mock_jira):
    '''
    Ensure pull_issues() calls connect()
    '''
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), [] ]

    pull_issues(mock_jira)
    assert mock_jira.connect.called


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__calls_load_issues_when_self_empty(mock_tqdm, mock_jira):
    '''
    Ensure pull_issues() calls load_issues() when self (a dict) is empty
    '''
    mock_jira.config.last_updated = '2019-01-01 00:00'
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), [] ]

    pull_issues(mock_jira)
    assert mock_jira.load_issues.called


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__calls_NOT_load_issues_when_self_populated(mock_tqdm, mock_jira):
    '''
    Ensure pull_issues() doesn't call load_issues() when self (a dict) already has issues
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    mock_jira.config.last_updated = '2019-01-01 00:00'
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), [] ]

    pull_issues(mock_jira)
    assert not mock_jira.load_issues.called


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__last_updated_field_creates_filter_query(mock_tqdm, mock_jira):
    '''
    Test config.last_updated being set causes a filtered query from value of last_updated
    '''
    mock_jira.config.last_updated = '2019-01-01 00:00'
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), [] ]

    pull_issues(mock_jira)

    # first calls, args (not kwargs), first arg
    assert mock_jira._jira.search_issues.call_args_list[0][0][0] == 'project IN (TEST) AND updated > "2019-01-01 00:00"'


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__last_updated_field_causes_filter_from_waaay_back(mock_tqdm, mock_jira):
    '''
    Test config.last_updated NOT being set causes a filtered query from 2010-01-01
    '''
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), [] ]

    pull_issues(mock_jira)

    # first calls, args (not kwargs), first arg
    assert mock_jira._jira.search_issues.call_args_list[0][0][0] == 'project IN (TEST) AND updated > "2010-01-01 00:00"'


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__error_handled_when_api_raises_jira_exception(mock_tqdm, mock_jira):
    '''
    Ensure an exception is raised and handled when the API raises a Jira exception
    '''
    mock_jira._jira.search_issues.side_effect = JiraApiError

    with pytest.raises(FailedPullingIssues):
        pull_issues(mock_jira)


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__write_issues_and_config_called(mock_tqdm, mock_jira):
    '''
    Test write_issues method is called
    Test config.write_to_disk method is called
    '''
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), [] ]

    pull_issues(mock_jira)
    assert mock_jira.config.write_to_disk.called


@mock.patch('jira_cli.sync.jiraapi_object_to_issue')
@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__adds_issues_to_self(mock_tqdm, mock_jiraapi_object_to_issue, mock_jira):
    '''
    Ensure that issues returned by search_issues(), are added to the Jira object (which implements dict)
    '''
    # mock Jira API to return two issues
    issues = [Issue.deserialize(ISSUE_1), Issue.deserialize(ISSUE_2)]
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=2), issues, [] ]

    # mock conversion function to return two Issues
    mock_jiraapi_object_to_issue.side_effect = issues

    assert len(mock_jira.keys()) == 0
    pull_issues(mock_jira)
    assert len(mock_jira.keys()) == 2


@mock.patch('jira_cli.sync.check_resolve_conflicts')
@mock.patch('jira_cli.sync.jiraapi_object_to_issue')
@mock.patch('jira_cli.sync.click')
def test_pull_issues__check_resolve_conflicts_NOT_called_when_updated_issue_NOT_changed(
        mock_click, mock_jiraapi_object_to_issue, mock_check_resolve_conflicts, mock_jira
    ):
    '''
    Check that check_resolve_conflict is NOT called when the Jira object is empty (ie have no issues)
    '''
    # mock search_issues to return single Issue
    issues = [Issue.deserialize(ISSUE_1)]
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), issues, [] ]

    # mock conversion function to return single Issue
    mock_jiraapi_object_to_issue.side_effect = [Issue.deserialize(ISSUE_1)]

    pull_issues(mock_jira)

    # no conflict is found
    assert mock_check_resolve_conflicts.called is False


@mock.patch('jira_cli.sync.check_resolve_conflicts')
@mock.patch('jira_cli.sync.jiraapi_object_to_issue')
@mock.patch('jira_cli.sync.click')
def test_pull_issues__check_resolve_conflicts_called_when_local_issue_is_modified(
        mock_click, mock_jiraapi_object_to_issue, mock_check_resolve_conflicts, mock_jira
    ):
    '''
    Check that check_resolve_conflict is called when the Jira object has the Issue already
    '''
    # preload the local cache with a modified issue
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock search_issues to return single object
    issues = [Issue.deserialize(ISSUE_1)]
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), issues, [] ]

    # mock conversion function to return single Issue
    mock_jiraapi_object_to_issue.side_effect = [Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)]

    pull_issues(mock_jira)

    # conflict found; resolve conflicts called
    assert mock_check_resolve_conflicts.called is True


@mock.patch('jira_cli.sync.check_resolve_conflicts')
@mock.patch('jira_cli.sync.jiraapi_object_to_issue')
@mock.patch('jira_cli.sync.click')
def test_pull_issues__return_from_check_resolve_conflicts_added_to_self(
        mock_click, mock_jiraapi_object_to_issue, mock_check_resolve_conflicts, mock_jira
    ):
    '''
    Check that return from check_resolve_conflict is added to Jira object (which implements dict)
    '''
    # preload the local cache with a modified issue
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock search_issues to return single object
    issues = [Issue.deserialize(ISSUE_1)]
    mock_jira._jira.search_issues.side_effect = [ mock.Mock(total=1), issues, [] ]

    modified_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)

    # mock conversion function to return single Issue
    mock_jiraapi_object_to_issue.side_effect = [modified_issue]

    modified_issue.assignee = 'undertest'

    # mock resolve_conflicts function to return modified_issue
    mock_check_resolve_conflicts.return_value = IssueUpdate(merged_issue=modified_issue)

    pull_issues(mock_jira)

    # validate that return from check_resolve_conflicts is added as TEST-71
    assert mock_jira['TEST-71'].assignee == 'undertest'

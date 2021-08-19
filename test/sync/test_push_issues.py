'''
Tests for push_issues() in the sync module
'''
from unittest import mock
import uuid

from fixtures import ISSUE_1, ISSUE_NEW
from helpers import modified_issue_helper, setup_jira_dataframe_helper
from jira_offline.exceptions import JiraApiError
from jira_offline.models import Issue
from jira_offline.sync import IssueUpdate, push_issues


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__calls_fetch_and_check_resolve_once_per_issue(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    Ensure fetch_issue(), merge_issues() and issue_to_jiraapi_update() are called
    once per modified issue
    '''
    # Create an unchanged issue fixture
    issue_1 = Issue.deserialize(ISSUE_1)

    # Create two modified issue fixtures
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = modified_issue_helper(Issue.deserialize(ISSUE_1), assignee='hoganp')
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-73'}):
        issue_3 = modified_issue_helper(Issue.deserialize(ISSUE_1), fix_versions={'0.1', '0.2'})

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2, issue_3])

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        push_issues()

    assert mock_jira.fetch_issue.call_count == 2
    assert mock_merge_issues.call_count == 2
    assert mock_issue_to_jiraapi_update.call_count == 2


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__calls_update_issue_when_issue_has_an_id(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    When Issue.id is set, ensure update_issue() is called, and new_issue() is NOT called
    '''
    # Create a modified issue fixture
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-71'}):
        issue_1 = modified_issue_helper(Issue.deserialize(ISSUE_1), assignee='hoganp')

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1])

    # Mock merge_issues to return NO conflicts
    mock_merge_issues.return_value = IssueUpdate(merged_issue=issue_1)

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        push_issues()

    assert mock_jira.update_issue.called
    assert not mock_jira.new_issue.called


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__calls_new_issue_when_issue_doesnt_have_an_id(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    When Issue.id is NOT set, ensure new_issue() is called, and update_issue() is NOT called
    '''
    issue_1 = Issue.deserialize(ISSUE_NEW)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1])

    # mock merge_issues to return NO conflicts
    mock_merge_issues.return_value = IssueUpdate(merged_issue=issue_1)

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        push_issues()

    assert not mock_jira.update_issue.called
    assert mock_jira.new_issue.called


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__count_only_successful_new_issue_calls(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    Ensure that count reflects the total successful new_issue calls
    '''
    issue_1 = Issue.deserialize(ISSUE_NEW)

    issue_key = uuid.uuid4()
    with mock.patch.dict(ISSUE_NEW, {'key': issue_key}):
        issue_2 = Issue.deserialize(ISSUE_NEW)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    # Mock `sync.merge_issues` to return valid issues
    mock_merge_issues.side_effect = [
        IssueUpdate(merged_issue=mock_jira[ISSUE_NEW['key']]),
        IssueUpdate(merged_issue=mock_jira[issue_key]),
    ]

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        count = push_issues()

    assert mock_jira.new_issue.call_count == 2
    assert count == 2


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__count_only_successful_new_issue_calls_when_one_fails(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    Ensure that count reflects the total successful updates
    '''
    # Create two new issue fixtures
    issue_1 = Issue.deserialize(ISSUE_NEW)

    issue_key = uuid.uuid4()
    with mock.patch.dict(ISSUE_NEW, {'key': issue_key}):
        issue_2 = Issue.deserialize(ISSUE_NEW)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    # Mock an exception to occur on the second call to `jira.new_issue`
    mock_jira.new_issue.side_effect = [issue_1, JiraApiError]

    # Mock `sync.merge_issues` to return valid issues
    mock_merge_issues.side_effect = [
        IssueUpdate(merged_issue=issue_1),
        IssueUpdate(merged_issue=issue_2),
    ]

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        count = push_issues()

    assert mock_jira.new_issue.call_count == 2
    assert count == 1


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__count_only_successful_update_issue_calls(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    Ensure that count reflects the total successful updates
    '''
    # Create two modified issue fixtures
    issue_1 = modified_issue_helper(Issue.deserialize(ISSUE_1), assignee='hoganp')

    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = modified_issue_helper(Issue.deserialize(ISSUE_1), assignee='hoganp')

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    # Mock `sync.merge_issues` to return valid issues
    mock_merge_issues.side_effect = [
        IssueUpdate(merged_issue=issue_1),
        IssueUpdate(merged_issue=issue_2),
    ]

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        count = push_issues()

    assert mock_jira.update_issue.call_count == 2
    assert count == 2


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__count_only_successful_update_issue_calls_when_one_fails(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    Ensure that count reflects the total successful updates
    '''
    # Create two modified issue fixtures
    issue_1 = modified_issue_helper(Issue.deserialize(ISSUE_1), assignee='hoganp')

    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = modified_issue_helper(Issue.deserialize(ISSUE_1), assignee='hoganp')

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    # Mock an exception to occur on the second call to `jira.update_issue`
    mock_jira.update_issue.side_effect = [None, JiraApiError]

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        count = push_issues()

    assert mock_jira.update_issue.call_count == 2
    assert count == 1

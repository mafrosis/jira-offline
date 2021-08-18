'''
Tests for push_issues() in the sync module
'''
from unittest import mock
import uuid

from fixtures import (ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF, ISSUE_2,
                      ISSUE_NEW)
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
    # add an unchanged Issue and two modified Issues to the Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)
    mock_jira['TEST-71.1'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    mock_jira['TEST-71.2'] = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)

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
    # add a modified Issue to the Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock merge_issues to return NO conflicts
    mock_merge_issues.return_value = IssueUpdate(merged_issue=mock_jira['TEST-71'])

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
    # add a new Issue to the Jira dict
    mock_jira[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

    # mock merge_issues to return NO conflicts
    mock_merge_issues.return_value = IssueUpdate(merged_issue=mock_jira[ISSUE_NEW['key']])

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        push_issues()

    assert not mock_jira.update_issue.called
    assert mock_jira.new_issue.called


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__skips_issues_from_unconfigured_projects(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira
    ):
    '''
    Ensure issues from unconfigured projects are ignored
    '''
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_2)
    mock_jira['TEST-72'].project_id = 'notarealprojecthash'

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        push_issues()

    assert mock_jira.fetch_issue.call_count == 1
    assert mock_merge_issues.call_count == 1
    assert mock_issue_to_jiraapi_update.call_count == 1


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__count_only_successful_new_issue_calls(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira, project
    ):
    '''
    Ensure that count reflects the total successful new_issue calls
    '''
    # Create two new issue fixtures
    mock_jira[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW, project=project)

    issue_key = uuid.uuid4()
    with mock.patch.dict(ISSUE_NEW, {'key': issue_key}):
        mock_jira[issue_key] = Issue.deserialize(ISSUE_NEW, project)

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
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira, project
    ):
    '''
    Ensure that count reflects the total successful updates
    '''
    # Create two new issue fixtures
    mock_jira[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW, project=project)

    issue_key = uuid.uuid4()
    with mock.patch.dict(ISSUE_NEW, {'key': issue_key}):
        mock_jira[issue_key] = Issue.deserialize(ISSUE_NEW, project)

    # Mock an exception to occur on the second call to `jira.new_issue`
    mock_jira.new_issue.side_effect = [mock_jira[ISSUE_NEW['key']], JiraApiError]

    # Mock `sync.merge_issues` to return valid issues
    mock_merge_issues.side_effect = [
        IssueUpdate(merged_issue=mock_jira[ISSUE_NEW['key']]),
        IssueUpdate(merged_issue=mock_jira[issue_key]),
    ]

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        count = push_issues()

    assert mock_jira.new_issue.call_count == 2
    assert count == 1


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__count_only_successful_update_issue_calls(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira, project
    ):
    '''
    Ensure that count reflects the total successful updates
    '''
    # Create fixtures: two modified issues
    with mock.patch.dict(ISSUE_1_WITH_ASSIGNEE_DIFF, {'key': 'SYNC-1'}):
        mock_jira['SYNC-1'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF, project)
    with mock.patch.dict(ISSUE_1_WITH_FIXVERSIONS_DIFF, {'key': 'SYNC-2'}):
        mock_jira['SYNC-2'] = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF, project)

    # Mock `sync.merge_issues` to return valid issues
    mock_merge_issues.side_effect = [
        IssueUpdate(merged_issue=mock_jira['SYNC-1']),
        IssueUpdate(merged_issue=mock_jira['SYNC-2']),
    ]

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        count = push_issues()

    assert mock_jira.update_issue.call_count == 2
    assert count == 2


@mock.patch('jira_offline.sync.merge_issues')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__count_only_successful_update_issue_calls_when_one_fails(
        mock_issue_to_jiraapi_update, mock_merge_issues, mock_jira, project
    ):
    '''
    Ensure that count reflects the total successful updates
    '''
    # Create fixtures: two modified issues
    with mock.patch.dict(ISSUE_1_WITH_ASSIGNEE_DIFF, {'key': 'SYNC-1'}):
        mock_jira['SYNC-1'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF, project)
    with mock.patch.dict(ISSUE_1_WITH_FIXVERSIONS_DIFF, {'key': 'SYNC-2'}):
        mock_jira['SYNC-2'] = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF, project)

    # Mock an exception to occur on the second call to `jira.update_issue`
    mock_jira.update_issue.side_effect = [None, JiraApiError]

    with mock.patch('jira_offline.sync.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        count = push_issues()

    assert mock_jira.update_issue.call_count == 2
    assert count == 1

from unittest import mock

from fixtures import ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF, ISSUE_NEW
from jira_offline.models import Issue
from jira_offline.sync import IssueUpdate, push_issues


@mock.patch('jira_offline.sync.check_resolve_conflicts')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__calls_fetch_and_check_resolve_once_per_issue(
        mock_issue_to_jiraapi_update, mock_check_resolve_conflicts, mock_jira
    ):
    '''
    Ensure fetch_issue(), check_resolve_conflicts() and issue_to_jiraapi_update() are called
    once per modified issue
    '''
    # add an unchanged Issue and two modified Issues to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)
    mock_jira['issue2'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    mock_jira['issue3'] = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)

    push_issues(mock_jira)

    assert mock_jira.fetch_issue.call_count == 2
    assert mock_check_resolve_conflicts.call_count == 2
    assert mock_issue_to_jiraapi_update.call_count == 2


@mock.patch('jira_offline.sync.check_resolve_conflicts')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__calls_update_issue_when_issue_has_an_id(
        mock_issue_to_jiraapi_update, mock_check_resolve_conflicts, mock_jira
    ):
    '''
    When Issue.id is set, ensure update_issue() is called, and new_issue() is NOT called
    '''
    # add a modified Issue to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock check_resolve_conflicts to return NO conflicts
    mock_check_resolve_conflicts.return_value = IssueUpdate(merged_issue=mock_jira['issue1'])

    push_issues(mock_jira)

    assert mock_jira.update_issue.called
    assert not mock_jira.new_issue.called


@mock.patch('jira_offline.sync.check_resolve_conflicts')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__calls_new_issue_when_issue_doesnt_have_an_id(
        mock_issue_to_jiraapi_update, mock_check_resolve_conflicts, mock_jira
    ):
    '''
    When Issue.id is NOT set, ensure new_issue() is called, and update_issue() is NOT called
    '''
    # add a modified Issue to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_NEW)

    # mock check_resolve_conflicts to return NO conflicts
    mock_check_resolve_conflicts.return_value = IssueUpdate(merged_issue=mock_jira['issue1'])

    push_issues(mock_jira)

    assert not mock_jira.update_issue.called
    assert mock_jira.new_issue.called


@mock.patch('jira_offline.sync.check_resolve_conflicts')
@mock.patch('jira_offline.sync.issue_to_jiraapi_update')
def test_push_issues__skips_issues_from_unconfigured_projects(
        mock_issue_to_jiraapi_update, mock_check_resolve_conflicts, mock_jira
    ):
    '''
    Ensure issues from unconfigured projects are ignored
    '''
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    mock_jira['issue2'] = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)
    mock_jira['issue2'].project_id = 'notarealprojecthash'

    push_issues(mock_jira)

    assert mock_jira.fetch_issue.call_count == 1
    assert mock_check_resolve_conflicts.call_count == 1
    assert mock_issue_to_jiraapi_update.call_count == 1

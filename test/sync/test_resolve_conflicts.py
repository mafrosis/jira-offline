from unittest import mock

import pytest

from fixtures import ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF
from jira_cli.models import Issue
from jira_cli.sync import (check_resolve_conflicts, ConflictResolutionFailed,
                           IssueUpdate, manual_conflict_resolution)


@mock.patch('jira_cli.sync.manual_conflict_resolution')
@mock.patch('jira_cli.sync._build_update')
def test_check_resolve_conflicts__doesnt_call_conflict_resolution_on_NO_conflict(mock_build_update, mock_manual_conflict_resolution):
    '''
    Ensure that check_resolve_conflicts does NOT call manual_conflict_resolution when no conflicts found
    '''
    issue1 = Issue.deserialize(ISSUE_1)

    # mock _build_update to return NO conflicts
    mock_build_update.return_value = IssueUpdate(merged_issue=issue1)

    check_resolve_conflicts(issue1, issue1)

    # ensure build_update is called
    assert mock_build_update.called is True
    # ensure conflict resolution is NOT called
    assert mock_manual_conflict_resolution.called is False


@mock.patch('jira_cli.sync.manual_conflict_resolution')
@mock.patch('jira_cli.sync._build_update')
def test_check_resolve_conflicts__returns_result_of_manual_conflict_resolution(mock_build_update, mock_manual_conflict_resolution):
    '''
    Ensure that result of manual_conflict_resolution is returned
    '''
    merged_issue = Issue.deserialize(ISSUE_1)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock _build_update to return conflicts
    update_obj = IssueUpdate(
        merged_issue=merged_issue,
        modified={'assignee'},
        conflicts={'assignee': {'original': 'danil1', 'updated': 'hoganp', 'base': 'danil1'}}
    )
    mock_build_update.return_value = update_obj

    # mock manual_conflict_resolution to return updated issue
    mock_manual_conflict_resolution.return_value = updated_issue

    resolved_issue = check_resolve_conflicts(merged_issue, updated_issue)

    # ensure build_update AND manual_conflict_resolution are called
    mock_build_update.assert_called_once_with(merged_issue, updated_issue)
    mock_manual_conflict_resolution.assert_called_with(update_obj)

    # return value should match return from manual_conflict_resolution
    assert resolved_issue == updated_issue


@mock.patch('jira_cli.sync.click')
@mock.patch('jira_cli.sync.parse_editor_result')
def test_manual_conflict_resolution_retries_three_times_on_none_return(mock_parse_editor_result, mock_click):
    '''
    A return of None from click.edit() should result in three retries
    '''
    issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = IssueUpdate(
        merged_issue=issue,
        modified={'assignee'},
        conflicts={'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}}
    )

    # mock click.edit to return None, which will cause EditorFieldParseFailed to be raised
    mock_click.edit.return_value = None

    with pytest.raises(ConflictResolutionFailed):
        manual_conflict_resolution(update_obj)

    assert mock_click.edit.call_count == 3
    assert not mock_parse_editor_result.called


@mock.patch('jira_cli.sync.click')
@mock.patch('jira_cli.sync.parse_editor_result')
def test_manual_conflict_resolution_retries_three_times_on_blank_return(mock_parse_editor_result, mock_click):
    '''
    A return of blank from click.edit() should result in three retries
    '''
    issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = IssueUpdate(
        merged_issue=issue,
        modified={'assignee'},
        conflicts={'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}}
    )

    # mock click.edit to return '', which will cause EditorFieldParseFailed to be raised
    mock_click.edit.return_value = ''

    with pytest.raises(ConflictResolutionFailed):
        manual_conflict_resolution(update_obj)

    assert mock_click.edit.call_count == 3
    assert not mock_parse_editor_result.called


@mock.patch('jira_cli.sync.click')
@mock.patch('jira_cli.sync.parse_editor_result')
def test_manual_conflict_resolution_handles_three_error_strings_in_editor_return(mock_parse_editor_result, mock_click):
    '''
    There are three strings which indicate failure in a conflict resolution string edit
    Ensure they all raise correctly
    '''
    issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = IssueUpdate(
        merged_issue=issue,
        modified={'assignee'},
        conflicts={'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}}
    )

    # mock click.edit to return None, which will cause EditorFieldParseFailed to be raised
    mock_click.edit.side_effect = [['<<'], ['>>'], ['==']]

    with pytest.raises(ConflictResolutionFailed):
        manual_conflict_resolution(update_obj)

    assert mock_click.edit.call_count == 3
    assert not mock_parse_editor_result.called


@mock.patch('jira_cli.sync.click')
@mock.patch('jira_cli.sync.parse_editor_result')
def test_manual_conflict_resolution_contrived_success_case(mock_parse_editor_result, mock_click):
    '''
    If click.edit() returns a non-error, manual_conflict_resolution() should return the same Issue
    returned from parse_editor_result()
    '''
    incoming_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = IssueUpdate(
        merged_issue=incoming_issue,
        modified={'assignee'},
        conflicts={'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}}
    )

    # mock the return from parse_editor_result()
    mock_parse_editor_result.return_value = incoming_issue

    resolved_issue = manual_conflict_resolution(update_obj)

    assert resolved_issue == incoming_issue
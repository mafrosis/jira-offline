from unittest import mock

import pytest

from fixtures import ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF
from jira_offline.models import Issue
from jira_offline.sync import (merge_issues, ConflictResolutionFailed,
                               IssueUpdate, manual_conflict_resolution)


@mock.patch('jira_offline.sync.manual_conflict_resolution')
@mock.patch('jira_offline.sync.build_update')
def test_merge_issues__doesnt_call_conflict_resolution_on_NO_conflict(mock_build_update, mock_manual_conflict_resolution):
    '''
    Ensure that merge_issues does NOT call manual_conflict_resolution when no conflicts found
    '''
    issue1 = Issue.deserialize(ISSUE_1)

    # mock build_update to return NO conflicts
    mock_build_update.return_value = IssueUpdate(merged_issue=issue1)

    merge_issues(issue1, issue1, is_upstream_merge=True)

    # ensure build_update is called
    assert mock_build_update.called is True
    # ensure conflict resolution is NOT called
    assert mock_manual_conflict_resolution.called is False


def test_merge_issues__merged_issue_has_original_property_updated_to_match_upstream_issue():
    '''
    Ensure the Issue returned from merge_issues has an original property set to the serialized upstream
    Issue returned by the Jira server
    '''
    local_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = merge_issues(local_issue, updated_issue, is_upstream_merge=True)

    serialized_upstream_issue = updated_issue.serialize()
    del serialized_upstream_issue['diff_to_original']
    del serialized_upstream_issue['modified']

    # validate Issue.original updated to match `updated_issue`
    assert update_obj.merged_issue.original == serialized_upstream_issue


def test_merge_issues__merged_issue_has_diff_to_original():
    '''
    Ensure the Issue returned from merge_issues has a diff_to_original attribute
    '''
    local_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = merge_issues(local_issue, updated_issue, is_upstream_merge=True)

    assert update_obj.merged_issue.diff_to_original != []


@mock.patch('jira_offline.sync.build_update')
def test_merge_issues__is_upstream_merge_equals_true__merged_issue_original_equals_updated_issue(mock_build_update):
    '''
    Ensure the Issue returned from merge_issues has Issue.set_original() called,
    when is_upstream_merge=True
    '''
    local_issue = Issue.deserialize(ISSUE_1)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock build_update to return a valid IssueUpdate object
    update_obj = IssueUpdate(
        merged_issue=local_issue,
        modified={'assignee'},
    )
    mock_build_update.return_value = update_obj

    # confirm Issue.original matches `local_issue`
    assert update_obj.merged_issue.original == local_issue.serialize()

    update_obj = merge_issues(local_issue, updated_issue, is_upstream_merge=True)

    serialized_upstream_issue = updated_issue.serialize()
    del serialized_upstream_issue['diff_to_original']
    del serialized_upstream_issue['modified']

    # validate Issue.original updated to match `updated_issue`
    assert update_obj.merged_issue.original == serialized_upstream_issue


@mock.patch('jira_offline.sync.build_update')
def test_merge_issues__is_upstream_merge_equals_false__merged_issue_original_DOES_NOT_equal_updated_issue(mock_build_update):
    '''
    Ensure the Issue returned from merge_issues does not have Issue.set_original() called,
    when is_upstream_merge=False
    '''
    local_issue = Issue.deserialize(ISSUE_1)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock build_update to return a valid IssueUpdate object
    update_obj = IssueUpdate(
        merged_issue=local_issue,
        modified={'assignee'},
    )
    mock_build_update.return_value = update_obj

    # confirm Issue.original matches `local_issue`
    assert update_obj.merged_issue.original == local_issue.serialize()

    update_obj = merge_issues(local_issue, updated_issue, is_upstream_merge=False)

    # validate Issue.original still matches `local_issue`
    assert update_obj.merged_issue.original == local_issue.serialize()


@mock.patch('jira_offline.sync.manual_conflict_resolution')
@mock.patch('jira_offline.sync.build_update')
def test_merge_issues__calls_manual_conflict_resolution(mock_build_update, mock_manual_conflict_resolution):
    '''
    Ensure that manual_conflict_resolution is invoked when there are conflicts
    '''
    local_issue = Issue.deserialize(ISSUE_1)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    # mock build_update to return conflicts
    update_obj = IssueUpdate(
        merged_issue=local_issue,
        modified={'assignee'},
        conflicts={'assignee': {'original': 'danil1', 'updated': 'hoganp', 'base': 'danil1'}}
    )
    mock_build_update.return_value = update_obj

    update_obj = merge_issues(local_issue, updated_issue, is_upstream_merge=True)

    # ensure build_update AND manual_conflict_resolution are called
    mock_build_update.assert_called_once_with(local_issue, updated_issue)
    mock_manual_conflict_resolution.assert_called_with(update_obj)


@mock.patch('jira_offline.sync.click')
@mock.patch('jira_offline.sync.parse_editor_result')
def test_manual_conflict_resolution__retries_three_times_on_none_return(mock_parse_editor_result, mock_click):
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


@mock.patch('jira_offline.sync.click')
@mock.patch('jira_offline.sync.parse_editor_result')
def test_manual_conflict_resolution__retries_three_times_on_blank_return(mock_parse_editor_result, mock_click):
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


@mock.patch('jira_offline.sync.click')
@mock.patch('jira_offline.sync.parse_editor_result')
def test_manual_conflict_resolution__handles_three_error_strings_in_editor_return(mock_parse_editor_result, mock_click):
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

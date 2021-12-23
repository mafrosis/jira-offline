from unittest import mock

import pytest

from conftest import not_raises
from fixtures import ISSUE_1
from jira_offline.exceptions import EditorFieldParseFailed, EditorRepeatFieldFound
from jira_offline.models import Issue
from jira_offline.cli.utils import parse_editor_result


def test_parse_editor_result__handles_str_change(project):
    '''
    Ensure editor parser handles a simple changed string
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          mafro',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
    )
    assert patch_dict['assignee'] == 'mafro'


def test_parse_editor_result__handles_str_change_over_100_chars(project):
    '''
    Ensure editor parser handles strings over 100 chars, as they are textwrapped for the editor
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          danil1',
        'Story Points',
        'Description       {}'.format('This is a story or issue ' * 5),  # pylint: disable=consider-using-f-string
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
    )
    assert patch_dict['description'] == str('This is a story or issue '*5).strip()


def test_parse_editor_result__parses_summary_str(project):
    '''
    Ensure editor parser handles unique summary string formatting
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          danil1',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
    )
    assert patch_dict['summary'] == 'This is the story summary'


def test_parse_editor_result__handles_extended_customfield(project):
    '''
    Ensure editor parser handles an extended customfield on an Issue
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          mafro',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Arbitrary Key     arbitrary_updated',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    # Set an extended customfield on the issue
    with mock.patch.dict(ISSUE_1, {'extended': {'arbitrary_key': 'arbitrary_value'}}):
        patch_dict = parse_editor_result(
            Issue.deserialize(ISSUE_1, project),
            '\n'.join(editor_result_raw),
        )

    assert patch_dict['extended.arbitrary_key'] == 'arbitrary_updated'


def test_parse_editor_result__handles_add_to_set(project):
    '''
    Ensure editor parser handles adding items to a set
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          danil1',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       - 0.1',
        '                  - 0.3',
        ' - DAVE',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
    )
    assert patch_dict['fix_versions'] == {'0.1', '0.3', 'DAVE'}


def test_parse_editor_result__handles_remove_from_set(project):
    '''
    Ensure editor parser handles removing items from a set
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-72] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          danil1',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version',
        'Labels            - bacon',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    with mock.patch.dict(ISSUE_1, {'labels': ['egg', 'bacon']}):
        patch_dict = parse_editor_result(
            Issue.deserialize(ISSUE_1, project),
            '\n'.join(editor_result_raw),
        )
    assert patch_dict['labels'] == {'bacon'}


def test_parse_editor_result__set_empty_items_ignored(project):
    '''
    Ensure editor parser handles bad input set set types
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        '-',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
    )
    assert patch_dict['fix_versions'] == {'0.1'}


@pytest.mark.parametrize('story_points', [99, 1.5])
def test_parse_editor_result__handles_decimal_type(story_points, project):
    '''
    Ensure editor parser handles decimal type
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          danil1',
        f'Story Points      {story_points}',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
    )
    assert patch_dict['story_points'] == str(story_points)


def test_parse_editor_result__raises_if_single_field_returned_twice(project):
    '''
    Ensure editor parser raises if a single field is returned twice from the editor
    '''
    editor_result_raw = [
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          High',
        'Assignee          mafro',
        'Assignee          hoganp',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    with pytest.raises(EditorRepeatFieldFound):
        parse_editor_result(
            Issue.deserialize(ISSUE_1, project),
            '\n'.join(editor_result_raw),
        )


@pytest.mark.parametrize('prefix', [
    '',
    ' ',
    'Summ',
])
def test_parse_editor_result__skips_lines_before_a_valid_field(prefix, project):
    '''
    Ensure editor parser skips any lines before a valid field name is found
    '''
    editor_result_raw = [
        prefix,
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          Normal',
        'Assignee          mafro',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
    )
    assert patch_dict['assignee'] == 'mafro'


def test_parse_editor_result__conflict__returns_only_changes_named_in_conflicts(project):
    '''
    Ensure editor parser in conflict mode returns only the changes made to conflicting fields
    '''
    editor_result_raw = [
        '# Conflict(s) on Issue TEST-71',
        ' ',
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          High',
        'Assignee          mafro',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    patch_dict = parse_editor_result(
        Issue.deserialize(ISSUE_1, project),
        '\n'.join(editor_result_raw),
        conflicts={'assignee'},
    )
    assert 'priority' not in patch_dict
    assert list(patch_dict.keys()) == ['assignee']
    assert patch_dict['assignee'] == 'mafro'


@pytest.mark.parametrize('bad_conflict', [
    '<<<<>>> updated',
    '<<',
    '>>',
    '==',
    ' ==',
])
def test_parse_editor_result__conflict__handles_bad_conflict_strings(bad_conflict, project):
    '''
    Ensure editor parser in conflict mode handles dodgy output from the editor
    '''
    editor_result_raw = [
        '# Conflict(s) on Issue TEST-71',
        ' ',
        '----------------  --------------------------------------',
        'Summary           [TEST-71] This is the story summary',
        'Type              Story',
        'Epic Ref',
        'Status            Story Done',
        'Priority          High',
        f'{bad_conflict}',
        'Story Points',
        'Description       This is a story or issue',
        'Fix Version       -  0.1',
        'Labels',
        'Reporter          danil1',
        'Creator           danil1',
        'Created           a year ago [2018-09-24 08:44:06+10:00]',
        'Updated           a year ago [2018-09-24 08:44:06+10:00]',
        'Last Viewed       a year ago [2018-09-24 08:44:06+10:00]',
        '----------------  --------------------------------------',
    ]

    with not_raises(EditorFieldParseFailed):
        parse_editor_result(
            Issue.deserialize(ISSUE_1, project),
            '\n'.join(editor_result_raw),
            conflicts={'assignee'},
        )

from fixtures import ISSUE_1
from jira_offline.models import Issue
from jira_offline.utils.cli import parse_editor_result


def test_parse_editor_result__handles_str_type():
    '''
    Ensure editor text parser handles string type
    '''
    editor_result_raw = '# Conflict(s) on Issue TEST-71\n\n----------------  --------------------------------------\nSummary           [TEST-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          {assignee}\nEstimate\nDescription       This is a story or issue\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        assignee='hoganp',
    )

    edited_issue = parse_editor_result(
        Issue.deserialize(ISSUE_1),
        editor_result_raw,
        conflicts={'assignee'},
    )
    assert edited_issue.assignee == 'hoganp'


def test_parse_editor_result__handles_str_type_over_100_chars():
    '''
    Ensure editor text parser handles strings over 100 chars, as they are textwrapped for the editor
    '''
    editor_result_raw = '# Conflict(s) on Issue TEST-71\n\n----------------  --------------------------------------\nSummary           [TEST-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          danil1\nEstimate\nDescription       {description}\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        description='This is a story or issue '*5,
    )

    edited_issue = parse_editor_result(
        Issue.deserialize(ISSUE_1),
        editor_result_raw,
        conflicts={'description'},
    )
    assert edited_issue.description == str('This is a story or issue '*5).strip()


def test_parse_editor_result__parses_summary_str():
    '''
    Ensure editor text parser handles unique summary string formatting
    '''
    editor_result_raw = '# Conflict(s) on Issue TEST-71\n\n----------------  --------------------------------------\nSummary           [TEST-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          danil1\nEstimate\nDescription       This is a story or issue\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'

    edited_issue = parse_editor_result(
        Issue.deserialize(ISSUE_1),
        editor_result_raw,
        conflicts={'summary'},
    )
    assert edited_issue.summary == 'This is the story summary'


def test_parse_editor_result__handles_set_type():
    '''
    Ensure editor text parser handles set type
    '''
    editor_result_raw = '# Conflict(s) on Issue TEST-71\n\n----------------  --------------------------------------\nSummary           [TEST-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          danil1\nEstimate\nDescription       This is a story or issue\nFix Version{fix_versions}\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        fix_versions='       -  0.1\n       -  0.3',
    )

    edited_issue = parse_editor_result(
        Issue.deserialize(ISSUE_1),
        editor_result_raw,
        conflicts={'fix_versions'},
    )
    assert edited_issue.fix_versions == {'0.1', '0.3'}


def test_parse_editor_result__handles_int_type():
    '''
    Ensure editor text parser handles int type
    '''
    editor_result_raw = '# Conflict(s) on Issue TEST-71\n\n----------------  --------------------------------------\nSummary           [TEST-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          danil1\nEstimate        {estimate}\nDescription       This is a story or issue\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        estimate='99',
    )

    edited_issue = parse_editor_result(
        Issue.deserialize(ISSUE_1),
        editor_result_raw,
        conflicts={'estimate'},
    )
    assert edited_issue.estimate == 99

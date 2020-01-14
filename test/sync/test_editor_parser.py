from jira_cli.models import Issue, IssueStatus
from jira_cli.sync import IssueUpdate, parse_editor_result

from fixtures import ISSUE_1


def test_parse_editor_result__handles_str_type():
    '''
    Ensure editor text parser handles string type
    '''
    editor_result_raw = '# Conflict(s) on Issue CNTS-71\n\n----------------  --------------------------------------\nSummary           [CNTS-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          {assignee}\nEstimate\nDescription       This is a story or issue\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        assignee='hoganp',
    )

    edited_issue = parse_editor_result(
        IssueUpdate(merged_issue=Issue.deserialize(ISSUE_1), conflicts={'assignee'}),
        editor_result_raw,
    )
    assert edited_issue.assignee == 'hoganp'


def test_parse_editor_result__handles_str_type_over_100_chars():
    '''
    Ensure editor text parser handles strings over 100 chars, as they are textwrapped for the editor
    '''
    editor_result_raw = '# Conflict(s) on Issue CNTS-71\n\n----------------  --------------------------------------\nSummary           [CNTS-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          danil1\nEstimate\nDescription       {description}\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        description='This is a story or issue '*5,
    )

    edited_issue = parse_editor_result(
        IssueUpdate(merged_issue=Issue.deserialize(ISSUE_1), conflicts={'description'}),
        editor_result_raw,
    )
    assert edited_issue.description == str('This is a story or issue '*5).strip()


def test_parse_editor_result__handles_set_type():
    '''
    Ensure editor text parser handles set type
    '''
    editor_result_raw = '# Conflict(s) on Issue CNTS-71\n\n----------------  --------------------------------------\nSummary           [CNTS-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          danil1\nEstimate\nDescription       This is a story or issue\nFix Version{fixVersions}\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        fixVersions='       -  0.1\n       -  0.3',
    )

    edited_issue = parse_editor_result(
        IssueUpdate(merged_issue=Issue.deserialize(ISSUE_1), conflicts={'fixVersions'}),
        editor_result_raw,
    )
    assert edited_issue.fixVersions == {'0.1', '0.3'}


def test_parse_editor_result__handles_enum_type():
    '''
    Ensure editor text parser handles enum type
    '''
    editor_result_raw = '# Conflict(s) on Issue CNTS-71\n\n----------------  --------------------------------------\nSummary           [CNTS-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            {status}\nPriority          Normal\nAssignee          danil1\nEstimate\nDescription       This is a story or issue\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        status=IssueStatus.NotAssessed.value,
    )

    edited_issue = parse_editor_result(
        IssueUpdate(merged_issue=Issue.deserialize(ISSUE_1), conflicts={'status'}),
        editor_result_raw,
    )
    assert edited_issue.status == IssueStatus.NotAssessed


def test_parse_editor_result__handles_int_type():
    '''
    Ensure editor text parser handles int type
    '''
    editor_result_raw = '# Conflict(s) on Issue CNTS-71\n\n----------------  --------------------------------------\nSummary           [CNTS-71] This is the story summary\nType              Story\nEpic Ref          EPIC-60\nStatus            Story Done\nPriority          Normal\nAssignee          danil1\nEstimate        {estimate}\nDescription       This is a story or issue\nFix Version       -  0.1\nLabels\nReporter          danil1\nCreator           danil1\nCreated           a year ago [2018-09-24 08:44:06+10:00]\nUpdated           a year ago [2018-09-24 08:44:06+10:00]\nLast Viewed       a year ago [2018-09-24 08:44:06+10:00]\n----------------  --------------------------------------\n'.format(
        estimate='99',
    )

    edited_issue = parse_editor_result(
        IssueUpdate(merged_issue=Issue.deserialize(ISSUE_1), conflicts={'estimate'}),
        editor_result_raw,
    )
    assert edited_issue.estimate == 99

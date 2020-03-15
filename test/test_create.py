import copy

import pytest

from fixtures import EPIC_1, ISSUE_1
from jira_cli.exceptions import EpicNotFound, SummaryAlreadyExists
from jira_cli.create import create_issue
from jira_cli.models import Issue, IssueStatus


def test_create__create_issue__loads_issues_when_cache_empty(mock_jira, project):
    '''
    Ensure create_issue() calls load_issues() when the cache is empty
    '''
    create_issue(mock_jira, project, 'Story', 'This is a summary')

    assert mock_jira.load_issues.called


def test_create__create_issue__does_not_load_issues_when_cache_full(mock_jira, project):
    '''
    Ensure create_issue() NOT calls load_issues() when the cache is full
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    create_issue(mock_jira, project, 'Story', 'This is a summary')

    assert not mock_jira.load_issues.called


def test_create__create_issue__adds_issue_to_self_and_calls_write_issues(mock_jira, project):
    '''
    Ensure create_issue() adds the new Issue to self, and writes the issue cache
    '''
    offline_issue = create_issue(mock_jira, project, 'Story', 'This is a summary')

    assert mock_jira[offline_issue.key]
    assert mock_jira.write_issues.called


def test_create__create_issue__mandatory_fields_are_set_in_new_issue(mock_jira, project):
    '''
    Ensure create_issue() sets the mandatory fields passed as args (not kwargs)
    '''
    offline_issue = create_issue(mock_jira, project, 'Story', 'This is a summary')

    assert offline_issue.project == 'TEST'
    assert offline_issue.issuetype == 'Story'
    assert offline_issue.summary == 'This is a summary'
    assert offline_issue.description == ''
    assert len(offline_issue.key) == 36  # UUID


def test_create__create_issue__creates_issues_with_unspecified_status(mock_jira, project):
    '''
    Ensure create_issue() sets Issue.status == IssueStatus.Unspecified on new issues
    '''
    offline_issue = create_issue(mock_jira, project, 'Story', 'This is a summary')

    assert offline_issue.status == IssueStatus.Unspecified


def test_create__create_issue__error_on_existing_summary_for_same_project(mock_jira, project):
    '''
    Check that create_issue() raises an error where summary string already exists for same project
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)
    mock_jira['issue1'].project = 'TEST'

    with pytest.raises(SummaryAlreadyExists):
        create_issue(mock_jira, project, 'Story', mock_jira['issue1'].summary)


def test_create__create_issue__NO_error_on_existing_summary_for_different_project(mock_jira, project):
    '''
    Check that create_issue() NO error raised on error where summary string already exists on a
    different project (means it's likely a duplicate)
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    unknown_project = copy.deepcopy(project)
    unknown_project.key = 'UNKN'

    offline_issue = create_issue(mock_jira, unknown_project, 'Story', mock_jira['issue1'].summary)
    assert len(offline_issue.key) == 36  # UUID


def test_create__create_issue__raises_exception_when_passed_an_unknown_epic_ref(mock_jira, project):
    '''
    Ensure create_issue() raises exception when an epic_ref is passed which does not match an
    existing epic on either summary OR epic_name
    '''
    # add an Epic fixture to the Jira dict
    mock_jira['epic1'] = Issue.deserialize(EPIC_1)

    with pytest.raises(EpicNotFound):
        create_issue(mock_jira, project, 'Story', 'This is summary', epic_ref='Nothing')


@pytest.mark.parametrize('epic_ref_value', [
    ('This is an epic'),
    ('0.1: Epic about a thing'),
])
def test_create__create_issue__issue_is_mapped_to_existing_epic_summary(mock_jira, project, epic_ref_value):
    '''
    Ensure create_issue() maps new Issue to the matching epic,
    when supplied epic_ref matches the epic's summary OR epic_name
    '''
    # add an Epic fixture to the Jira dict
    mock_jira['epic1'] = Issue.deserialize(EPIC_1)

    new_issue = create_issue(mock_jira, project, 'Story', 'This is summary', epic_ref=epic_ref_value)

    # assert new Issue to linked to the epic
    assert new_issue.epic_ref == mock_jira['epic1'].key

from unittest import mock

from fixtures import EPIC_1, ISSUE_1
from helpers import setup_jira_dataframe_helper
from jira_offline.models import Issue
from jira_offline.linters import fix_versions


def test_lint__fix_versions__finds_empty_fix_versions_field(mock_jira):
    '''
    Ensure lint fix_versions returns Issues with empty fix_versions field
    '''
    # Create the epic to which ISSUE_1 is linked
    epic_1 = Issue.deserialize(EPIC_1)

    with mock.patch.dict(ISSUE_1, {'fix_versions': set()}):
        issue_1 = Issue.deserialize(ISSUE_1)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([epic_1, issue_1])

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        df = fix_versions(fix=False)

    # Assert single issue with missing fix_versions
    assert len(df) == 1


def test_lint__fix_versions__fix_updates_an_issues_linked_to_epic(mock_jira):
    '''
    Ensure lint fix_versions updates an issue linked the epic when fix=True
    '''
    # Create the epic to which ISSUE_1 is linked
    epic_1 = Issue.deserialize(EPIC_1)

    with mock.patch.dict(ISSUE_1, {'fix_versions': set()}):
        issue_1 = Issue.deserialize(ISSUE_1)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([epic_1, issue_1])

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        df = fix_versions(fix=True, value='0.1')

    # Assert no issues with missing fix_versions
    assert len(df) == 0
    # Assert issue was fixed
    assert mock_jira['TEST-71'].fix_versions == {'0.1'}
    assert mock_jira.write_issues.called


def test_lint__fix_versions__respect_the_filter(mock_jira):
    '''
    Ensure lint fix_versions respects a filter set in jira.filter
    '''
    with mock.patch.dict(ISSUE_1, {'fix_versions': set(), 'assignee': 'bob'}):
        issue_1 = Issue.deserialize(ISSUE_1)
    with mock.patch.dict(ISSUE_1, {'fix_versions': set(), 'assignee': 'dave', 'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    # Set the filter
    mock_jira.filter.set('assignee = bob')

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        df = fix_versions()

    # Assert correct number issues missing fix_versions
    assert len(df) == 1

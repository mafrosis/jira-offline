from unittest import mock

from fixtures import ISSUE_1
from helpers import setup_jira_dataframe_helper
from jira_offline.models import Issue
from jira_offline.linters import issues_missing_epic


def test_lint__issues_missing_epic__finds_issues_missing_epic(mock_jira, project):
    '''
    Ensure lint issues_missing_epic returns Issues missing the epic_link field
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'epic_link': None, 'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        df = issues_missing_epic(fix=False)

    # Assert single issue missing an epic
    assert len(df) == 1


def test_lint__issues_missing_epic__fix_updates_an_issue(mock_jira, project):
    '''
    Ensure lint issues_missing_epic sets epic_link of an issue when fix=True
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'epic_link': None, 'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        df = issues_missing_epic(fix=True, epic_link='EGG-1234')

    # Assert no issues missing an epic
    assert len(df) == 0
    # Assert issue was fixed
    assert mock_jira['TEST-72'].epic_link == 'EGG-1234'
    assert mock_jira.write_issues.called


def test_lint__issues_missing_epic__respect_the_filter(mock_jira, project):
    '''
    Ensure lint issues_missing_epic respects a filter set in jira.filter
    '''
    with mock.patch.dict(ISSUE_1, {'epic_link': None, 'assignee': 'bob'}):
        issue_1 = Issue.deserialize(ISSUE_1, project)
    with mock.patch.dict(ISSUE_1, {'epic_link': None, 'assignee': 'dave', 'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    # Set the filter
    mock_jira.filter.set('assignee = bob')

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        df = issues_missing_epic()

    # Assert correct number issues missing fix_versions
    assert len(df) == 1

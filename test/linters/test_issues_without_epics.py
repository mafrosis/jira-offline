from unittest import mock

import pytest

from fixtures import ISSUE_2, ISSUE_MISSING_EPIC, ISSUE_DIFF_PROJECT
from jira_offline.models import Issue
from jira_offline.linters import issues_missing_epic


def test_lint__issues_missing_epic__finds_issues_missing_epic(mock_jira):
    '''
    Ensure lint issues_missing_epic returns Issues missing the epic_link field
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_2)
    mock_jira['TEST-73'] = Issue.deserialize(ISSUE_MISSING_EPIC)

    # assert two issues in Jira
    assert len(mock_jira._df) == 2

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        df = issues_missing_epic(fix=False)

    # assert single issue missing an epic
    assert len(df) == 1


def test_lint__issues_missing_epic__fix_updates_an_issue(mock_jira):
    '''
    Ensure lint issues_missing_epic sets epic_link of an issue when fix=True
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_2)
    mock_jira['TEST-73'] = Issue.deserialize(ISSUE_MISSING_EPIC)

    # assert issue has an empty epic_link
    assert mock_jira['TEST-73'].epic_link is None

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        df = issues_missing_epic(fix=True, epic_link='EGG-1234')

    # assert no issues missing an epic
    assert len(df) == 0
    # assert issue3's epic_link has been updated
    assert mock_jira['TEST-73'].epic_link == 'EGG-1234'
    # ensure changes written to disk
    assert mock_jira.write_issues.called


@pytest.mark.parametrize('project_filter,number_issues_missing_fix_versions', [
    (None, 2),
    ('TEST', 0),
])
def test_lint__issues_missing_epic__respect_the_filter(mock_jira, project_filter, number_issues_missing_fix_versions):
    '''
    Ensure lint issues_missing_epic respects a filter set in jira.filter
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_2)
    mock_jira['TEST-73'] = Issue.deserialize(ISSUE_MISSING_EPIC)
    mock_jira['EGG-99'] = Issue.deserialize(ISSUE_DIFF_PROJECT)

    if project_filter is not None:
        # set the filter
        mock_jira.filter.set(f'project = {project_filter}')

    with mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        df = issues_missing_epic()

    # assert correct number issues missing fix_versions
    assert len(df) == number_issues_missing_fix_versions

from unittest import mock

import pytest

from fixtures import EPIC_1, ISSUE_1, ISSUE_DIFF_PROJECT
from jira_offline.models import Issue
from jira_offline.linters import fix_versions


def test_lint__fix_versions__finds_empty_fix_versions_field(mock_jira):
    '''
    Ensure lint fix_versions returns Issues with empty fix_versions field
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    # add fixture without a fix_versions value
    issue_1 = Issue.deserialize(ISSUE_1)
    issue_1.fix_versions.clear()
    mock_jira['TEST-71'] = issue_1

    # assert two issues in Jira
    assert len(mock_jira.df) == 2

    with mock.patch('jira_offline.linters.jira', mock_jira):
        df = fix_versions(fix=False)

    # assert single issue with missing fix_versions
    assert len(df) == 1


def test_lint__fix_versions__fix_updates_an_issues_linked_to_epic(mock_jira):
    '''
    Ensure lint fix_versions updates an issue linked the epic when fix=True
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    # add fixture without a fix_versions value
    issue_1 = Issue.deserialize(ISSUE_1)
    issue_1.fix_versions.clear()
    mock_jira['TEST-71'] = issue_1

    with mock.patch('jira_offline.linters.jira', mock_jira):
        df = fix_versions(fix=True, value='0.1')

    # assert no issues with missing fix_versions
    assert len(df) == 0
    # assert fix_versions has been updated on the issue
    assert mock_jira['TEST-71'].fix_versions == {'0.1'}
    # ensure changes written to disk
    assert mock_jira.write_issues.called


@pytest.mark.parametrize('project_filter,number_issues_missing_fix_versions', [
    (None, 1),
    ('TEST', 0),
])
def test_lint__fix_versions__respects_the_filters(mock_jira, project_filter, number_issues_missing_fix_versions):
    '''
    Ensure lint fix_versions respects any filters set in IssueFilter
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)
    mock_jira['EGG-99'] = Issue.deserialize(ISSUE_DIFF_PROJECT)

    # set the filter
    mock_jira.filter.project_key = project_filter

    with mock.patch('jira_offline.linters.jira', mock_jira):
        df = fix_versions()

    # assert correct number issues missing fix_versions
    assert len(df) == number_issues_missing_fix_versions

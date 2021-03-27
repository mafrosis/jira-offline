import pytest

from fixtures import ISSUE_2, ISSUE_MISSING_EPIC, ISSUE_DIFF_PROJECT
from jira_offline.models import Issue
from jira_offline.linters import issues_missing_epic


def test_lint__issues_missing_epic__finds_issues_missing_epic(mock_jira):
    '''
    Ensure lint issues_missing_epic returns Issues missing the epic_ref field
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_2)
    mock_jira['TEST-73'] = Issue.deserialize(ISSUE_MISSING_EPIC)

    # assert two issues in Jira
    assert len(mock_jira.df) == 2

    df = issues_missing_epic(mock_jira, fix=False)

    # assert single issue missing an epic
    assert len(df) == 1


def test_lint__issues_missing_epic__fix_updates_an_issue(mock_jira):
    '''
    Ensure lint issues_missing_epic sets epic_ref of an issue when fix=True
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_2)
    mock_jira['TEST-73'] = Issue.deserialize(ISSUE_MISSING_EPIC)

    # assert issue has an empty epic_ref
    assert mock_jira['TEST-73'].epic_ref is None

    df = issues_missing_epic(mock_jira, fix=True, epic_ref='EGG-1234')

    # assert no issues missing an epic
    assert len(df) == 0
    # assert issue3's epic_ref has been updated
    assert mock_jira['TEST-73'].epic_ref == 'EGG-1234'
    # ensure changes written to disk
    assert mock_jira.write_issues.called


@pytest.mark.parametrize('project_filter,number_issues_missing_fix_versions', [
    (None, 2),
    ('TEST', 0),
])
def test_lint__issues_missing_epic__respects_the_filters(mock_jira, project_filter, number_issues_missing_fix_versions):
    '''
    Ensure lint issues_missing_epic respects any filters set in IssueFilter
    '''
    # add fixtures to Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_2)
    mock_jira['TEST-73'] = Issue.deserialize(ISSUE_MISSING_EPIC)
    mock_jira['EGG-99'] = Issue.deserialize(ISSUE_DIFF_PROJECT)

    # set the filter
    mock_jira.filter.project_key = project_filter

    df = issues_missing_epic(mock_jira)

    # assert correct number issues missing fix_versions
    assert len(df) == number_issues_missing_fix_versions

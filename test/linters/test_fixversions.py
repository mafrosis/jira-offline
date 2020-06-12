from fixtures import EPIC_1, ISSUE_1
from jira_offline.models import Issue
from jira_offline.linters import fix_versions


def test_lint_fix_versions_finds_empty_fix_versions_field(mock_jira):
    '''
    Ensure lint fix_versions returns Issues with empty fix_versions field
    '''
    # add fixtures to Jira dict
    mock_jira['epic1'] = Issue.deserialize(EPIC_1)
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    # empty fix_versions set
    mock_jira['issue1'].fix_versions.clear()

    # assert two issues in Jira
    assert len(mock_jira.df) == 2

    df = fix_versions(mock_jira, fix=False)

    # assert single issue with missing fix_versions
    assert len(df) == 1


def test_lint_fix_versions_fix_updates_an_issues_linked_to_epic(mock_jira):
    '''
    Ensure lint fix_versions updates an issue linked the epic when fix=True
    '''
    # add fixtures to Jira dict
    mock_jira['epic1'] = Issue.deserialize(EPIC_1)
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    # empty fix_versions set
    mock_jira['issue1'].fix_versions.clear()

    df = fix_versions(mock_jira, fix=True, value='0.1')

    # assert no issues with missing fix_versions
    assert len(df) == 0
    # assert fix_versions has been updated on the issue
    assert mock_jira['issue1'].fix_versions == {'0.1'}
    # ensure changes written to disk
    assert mock_jira.write_issues.called

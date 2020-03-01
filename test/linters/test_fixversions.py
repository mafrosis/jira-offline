from fixtures import EPIC_1, ISSUE_1
from jira_cli.models import Issue
from jira_cli.linters import fixversions


def test_lint_fixversions_finds_empty_fixversions_field(mock_jira):
    '''
    Ensure lint fixversions returns Issues with empty fixVersions field
    '''
    # add fixtures to Jira dict
    mock_jira['epic1'] = Issue.deserialize(EPIC_1)
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    # empty fixVersions set
    mock_jira['issue1'].fixVersions.clear()

    # assert two issues in Jira
    assert len(mock_jira.df) == 2

    df = fixversions(mock_jira, fix=False)

    # assert single issue with missing fixVersions
    assert len(df) == 1


def test_lint_fixversions_fix_updates_an_issues_linked_to_epic(mock_jira):
    '''
    Ensure lint fixversions updates an issue linked the epic when fix=True
    '''
    # add fixtures to Jira dict
    mock_jira['epic1'] = Issue.deserialize(EPIC_1)
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    # empty fixVersions set
    mock_jira['issue1'].fixVersions.clear()

    df = fixversions(mock_jira, fix=True, value='0.1')

    # assert no issues with missing fixVersions
    assert len(df) == 0
    # assert fixVersions has been updated on the issue
    assert mock_jira['issue1'].fixVersions == {'0.1'}
    # ensure changes written to disk
    assert mock_jira.write_issues.called

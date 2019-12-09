from unittest import mock

from jira_cli.main import Issue
from jira_cli.linters import fixversions
from test.fixtures import ISSUE_1, ISSUE_2


@mock.patch('jira_cli.linters.Jira')
def test_lint_fixversions_finds_empty_fixversions_field(mock_jira_local, mock_jira):
    '''
    Ensure CLI lint fixversions command returns Issues with empty fixVersions field
    '''
    # add fixtures to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)
    mock_jira['issue2'] = Issue.deserialize(ISSUE_2)

    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # assert two issues in Jira
    assert len(mock_jira.df) == 2

    df = fixversions(fix=False)

    # assert single issue with missing fixVersions
    assert len(df) == 1


@mock.patch('jira_cli.linters.Jira')
def test_lint_fixversions_fix_updates_an_issue(mock_jira_local, mock_jira):
    '''
    Ensure CLI lint fixversions command updates an issue when fix=True
    '''
    # add fixtures to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)
    mock_jira['issue2'] = Issue.deserialize(ISSUE_2)

    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # assert issue2 has an empty fixVersions
    assert mock_jira['issue2'].fixVersions == set()

    df = fixversions(fix=True, words=['0.1'])

    # assert no issues with missing fixVersions
    assert len(df) == 0
    # assert fixVersions has been updated
    assert mock_jira['issue2'].fixVersions == {'0.1'}
    # ensure changes written to disk
    assert mock_jira.write_issues.called

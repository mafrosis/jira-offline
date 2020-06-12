from unittest import mock

from click.testing import CliRunner
import pytest

from fixtures import ISSUE_1
from jira_offline.cli import cli
from jira_offline.main import Issue


STATS_SUBCOMMANDS = [
    'issuetype',
    'status',
    'fix-versions',
]


@pytest.mark.parametrize('subcommand', STATS_SUBCOMMANDS)
@mock.patch('jira_offline.cli.stats.Jira')
def test_stats_smoketest(mock_jira_local, mock_jira, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache has a
    single issue
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # add fixture to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()
    result = runner.invoke(cli, ['stats', subcommand])
    # CLI should always exit zero
    assert result.exit_code == 0


@pytest.mark.parametrize('subcommand', STATS_SUBCOMMANDS)
@mock.patch('jira_offline.cli.stats.Jira')
def test_stats_smoketest_empty(mock_jira_local, mock_jira, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache is empty
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['stats', subcommand])
    # CLI should always exit 1
    assert result.exit_code == 1


@mock.patch('jira_offline.cli.stats.Jira')
@mock.patch('jira_offline.cli.stats.print_table')
def test_cli_stats_no_errors_when_no_subcommand_passed(mock_print_table, mock_jira_local, mock_jira):
    '''
    Ensure no exceptions arise from the stats subcommands when no subcommand passed, and print table
    is called three times (as there are three subcommands to be invoked)
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # add fixture to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()
    result = runner.invoke(cli, ['stats'])
    assert result.exit_code == 0
    assert mock_print_table.call_count == 3

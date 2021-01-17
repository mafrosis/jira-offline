from unittest import mock

from click.testing import CliRunner
import pytest

from fixtures import ISSUE_1
from jira_offline.cli import cli
from jira_offline.jira import Issue


STATS_SUBCOMMANDS = [
    'issuetype',
    'status',
    'fix-versions',
]


@pytest.mark.parametrize('subcommand', STATS_SUBCOMMANDS)
@mock.patch('jira_offline.cli.stats.jira')
def test_stats_smoketest(mock_jira_proxy, mock_jira, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache has a
    single issue
    '''
    # set imported jira proxy to point at mock_jira
    mock_jira_proxy = mock_jira

    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()

    with mock.patch('jira_offline.cli.stats.jira', mock_jira):
        result = runner.invoke(cli, ['stats', subcommand])

    # CLI should always exit zero
    assert result.exit_code == 0


@pytest.mark.parametrize('subcommand', STATS_SUBCOMMANDS)
def test_stats_smoketest_empty(mock_jira, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache is empty
    '''
    runner = CliRunner()

    with mock.patch('jira_offline.cli.stats.jira', mock_jira):
        result = runner.invoke(cli, ['stats', subcommand])

    # CLI should always exit 1
    assert result.exit_code == 1


@mock.patch('jira_offline.cli.stats.jira')
@mock.patch('jira_offline.cli.stats.print_table')
def test_cli_stats__no_errors_when_no_subcommand_passed(mock_print_table, mock_jira_proxy, mock_jira):
    '''
    Ensure no exceptions arise from the stats subcommands when no subcommand passed, and print table
    is called three times (as there are three subcommands to be invoked)
    '''
    # set imported jira proxy to point at mock_jira
    mock_jira_proxy = mock_jira

    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()

    with mock.patch('jira_offline.cli.stats.jira', mock_jira):
        result = runner.invoke(cli, ['stats'])

    assert result.exit_code == 0
    assert mock_print_table.call_count == 3

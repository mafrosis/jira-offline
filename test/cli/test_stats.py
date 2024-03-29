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
def test_stats_smoketest(mock_jira, project, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache has a
    single issue
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.stats.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['stats', subcommand])

    # CLI should always exit zero
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize('subcommand', STATS_SUBCOMMANDS)
def test_stats_smoketest_empty(mock_jira, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache is empty
    '''
    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.stats.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['stats', subcommand])

    # CLI should always exit 1
    assert result.exit_code == 1, result.output


@mock.patch('jira_offline.cli.stats.print_table')
def test_cli_stats__no_errors_when_no_subcommand_passed(mock_print_table, mock_jira, project):
    '''
    Ensure no exceptions arise from the stats subcommands when no subcommand passed, and print table
    is called three times (as there are three subcommands to be invoked)
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.stats.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['stats'])

    assert result.exit_code == 0, result.output
    assert mock_print_table.call_count == 3

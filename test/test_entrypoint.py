from unittest import mock
import logging

from click.testing import CliRunner
import pandas as pd
import pytest

from jira_cli.main import Issue
from jira_cli.entrypoint import cli
from test.fixtures import ISSUE_1


@mock.patch('jira_cli.entrypoint.Jira')
def test_verbose_flag_sets_logger_to_info_level(mock_jira_local, mock_jira):
    '''
    Ensure the --verbose flag correctly sets the logger level
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    runner.invoke(cli, ['--verbose', 'show'])
    assert logging.getLogger('jira').level == logging.INFO


@mock.patch('jira_cli.entrypoint.Jira')
def test_debug_flag_sets_logger_to_debug_level(mock_jira_local, mock_jira):
    '''
    Ensure the --debug flag correctly sets the logger level
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    runner.invoke(cli, ['--debug', 'show'])
    assert logging.getLogger('jira').level == logging.DEBUG


@mock.patch('jira_cli.entrypoint.Jira')
def test_cli_show_no_errors(mock_jira_local, mock_jira):
    '''
    Ensure no exceptions arise from the show command
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # add fixture to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()
    result = runner.invoke(cli, ['show', 'issue1'])
    assert result.exit_code == 0
    assert mock_jira.load_issues.called


@mock.patch('jira_cli.entrypoint.pull_issues')
@mock.patch('jira_cli.entrypoint.Jira')
@mock.patch('jira_cli.entrypoint.load_config')
def test_cli_pull_no_errors(mock_load_config, mock_jira_local, mock_pull_issues, mock_jira):
    '''
    Ensure no exceptions arise from the pull command
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['pull'], catch_exceptions=False)
    assert result.exit_code == 0
    assert mock_load_config.called
    assert mock_pull_issues.called


@pytest.mark.parametrize('subcommand', [
    'issuetype', 'status', 'fixversions',
])
@mock.patch('jira_cli.entrypoint.Jira')
@mock.patch('jira_cli.entrypoint._print_table')
def test_cli_stats_no_errors(mock_print_table, mock_jira_local, mock_jira, subcommand):
    '''
    Ensure no exceptions arise from the stats subcommands
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # add fixture to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()
    result = runner.invoke(cli, ['stats', subcommand])
    assert result.exit_code == 0
    assert mock_print_table.called
    assert isinstance(mock_print_table.call_args_list[0][0][0], pd.DataFrame)


@mock.patch('jira_cli.entrypoint.Jira')
@mock.patch('jira_cli.entrypoint._print_table')
def test_cli_stats_no_errors_no_subcommand(mock_print_table, mock_jira_local, mock_jira):
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


@mock.patch('jira_cli.entrypoint.lint_fixversions')
def test_cli_lint_fixversions_echo(mock_lint_fixversions):
    '''
    Ensure lint fixversions command calls click.echo without error
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', 'fixversions'])
    assert result.exit_code == 0
    assert mock_lint_fixversions.called
    assert result.output.endswith(' issues missing the fixVersions field\n')


@mock.patch('jira_cli.entrypoint.lint_fixversions')
def test_cli_lint_fixversions_fix_requires_words(mock_lint_fixversions):
    '''
    Ensure lint fixversions with --fix param errors without --words
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'fixversions'])
    assert result.exit_code != 0
    assert result.output.endswith('You must pass --words with --fix\n')


@mock.patch('jira_cli.entrypoint.lint_fixversions')
def test_cli_lint_fixversions_fix_passes_words_to_lint_func(mock_lint_fixversions):
    '''
    Ensure lint fixversions with --fix and --words correctly calls lint_fixversions
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'fixversions', '--words', 'CNTS,TEST'])
    assert result.exit_code == 0
    mock_lint_fixversions.assert_called_with(True, {'CNTS', 'TEST'})


@mock.patch('jira_cli.entrypoint.lint_issues_missing_epic')
def test_cli_lint_issues_missing_epic_echo(mock_lint_issues_missing_epic):
    '''
    Ensure lint issues_missing_epic command calls click.echo without error
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', 'issues-missing-epic'])
    assert result.exit_code == 0
    assert mock_lint_issues_missing_epic.called
    assert result.output.endswith(' issues missing an epic\n')


@mock.patch('jira_cli.entrypoint.lint_issues_missing_epic')
def test_cli_lint_issues_missing_epic_fix_requires_epic_ref(mock_lint_issues_missing_epic):
    '''
    Ensure lint issues_missing_epic with --fix param errors without --epic-ref
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'issues-missing-epic'])
    assert result.exit_code != 0
    assert result.output.endswith('You must pass --epic_ref with --fix\n')


@mock.patch('jira_cli.entrypoint.lint_issues_missing_epic')
def test_cli_lint_issues_missing_epic_fix_passes_epic_ref_to_lint_func(mock_lint_issues_missing_epic):
    '''
    Ensure lint issues-missing-epic with --fix and --epic_ref correctly calls lint_issues_missing_epic
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'issues-missing-epic', '--epic-ref', 'CNTS'])
    assert result.exit_code == 0
    mock_lint_issues_missing_epic.assert_called_with(True, 'CNTS')

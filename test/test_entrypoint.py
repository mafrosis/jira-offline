import json
import logging
from unittest import mock

import click
from click.testing import CliRunner
import pytest

from fixtures import ISSUE_1
from jira_offline.entrypoint import cli
from jira_offline.main import Issue


@mock.patch('jira_offline.entrypoint.Jira')
def test_verbose_flag_sets_logger_to_info_level(mock_jira_local, mock_jira):
    '''
    Ensure the --verbose flag correctly sets the logger level
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    runner.invoke(cli, ['--verbose', 'show'])
    assert logging.getLogger('jira').level == logging.INFO


@mock.patch('jira_offline.entrypoint.Jira')
def test_debug_flag_sets_logger_to_debug_level(mock_jira_local, mock_jira):
    '''
    Ensure the --debug flag correctly sets the logger level
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    runner.invoke(cli, ['--debug', 'show'])
    assert logging.getLogger('jira').level == logging.DEBUG


# 0: CLI command name
# 1: tuple of "basic" parameters to pass
# 2: expected return code when Jira dict is empty (used in test_cli_smoketest_empty)
CLI_COMMAND_MAPPING = [
    ('projects', tuple(), 0),
    ('ls', tuple(), 1),
    ('show', ('issue1',), 1),
    ('clone', ('https://jira.atlassian.com/TEST1',), 0),
    ('new', ('TEST', 'Story', 'Summary'), 0),
    ('pull', tuple(), 0),
    ('push', tuple(), 1),
    ('edit', ('issue1', '--summary', 'Egg'), 1),
    ('stats', ('issuetype',), 1),
    ('stats', ('status',), 1),
    ('stats', ('fixversions',), 1),
    ('lint', ('fixversions',), 1),
    ('lint', ('issues-missing-epic',), 1),
]


@pytest.mark.parametrize('command,params,_', CLI_COMMAND_MAPPING)
@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint.create_issue')
@mock.patch('jira_offline.entrypoint.pull_single_project')
@mock.patch('jira_offline.entrypoint.pull_issues')
@mock.patch('jira_offline.entrypoint.push_issues')
@mock.patch('jira_offline.entrypoint.authenticate')
def test_cli_smoketest(mock_authenticate, mock_push_issues, mock_pull_issues,
                       mock_pull_single_project, mock_create_issue,
                       mock_jira_local, mock_jira, command, params, _):
    '''
    Dumb smoke test function to check for errors in application CLI
    Failures here often uncover untested parts of the codebase

    This function tests when the jira-offline issue cache has a single issue
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # add fixture to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()
    result = runner.invoke(cli, [command, *params])
    # CLI should always exit zero
    assert result.exit_code == 0


@pytest.mark.parametrize('command,params,exit_code', CLI_COMMAND_MAPPING)
@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint.create_issue')
@mock.patch('jira_offline.entrypoint.pull_single_project')
@mock.patch('jira_offline.entrypoint.pull_issues')
@mock.patch('jira_offline.entrypoint.push_issues')
@mock.patch('jira_offline.entrypoint.authenticate')
def test_cli_smoketest_empty(mock_authenticate, mock_push_issues, mock_pull_issues,
                             mock_pull_single_project, mock_create_issue,  mock_jira_local,
                             mock_jira, command, params, exit_code):
    '''
    Dumb smoke test function to check for errors in application CLI
    Failures here often uncover untested parts of the codebase

    This function tests when the jira-offline issue cache is empty
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, [command, *params])
    # some CLI commands will exit with error, others will not..
    assert result.exit_code == exit_code


@mock.patch('jira_offline.entrypoint.Jira')
def test_cli_show_invalid_issue_key(mock_jira_local, mock_jira):
    '''
    Ensure show command errors when passed an invalid/missing Issue key
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['show', 'issue1'])
    assert result.exit_code == 1
    assert result.output == 'Unknown issue key\nAborted!\n'


@mock.patch('jira_offline.entrypoint.Jira')
def test_cli_show_can_return_json(mock_jira_local, mock_jira):
    '''
    Ensure show command can return output as JSON
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # add fixture to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()
    result = runner.invoke(cli, ['show', '--json', 'issue1'])
    assert result.exit_code == 0
    try:
        json.loads(f'{result.output}')
    except json.decoder.JSONDecodeError:
        pytest.fail('Invalid JSON returned!')


@mock.patch('jira_offline.entrypoint.pull_issues')
@mock.patch('jira_offline.entrypoint.Jira')
def test_cli_pull_reset_hard_flag_calls_confirm_abort(mock_jira_local, mock_pull_issues, mock_jira):
    '''
    Ensure pull --reset-hard calls click.confirm() with abort=True flag
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    click.confirm = mock_click_confirm = mock.Mock(side_effect=click.exceptions.Abort)

    runner = CliRunner()
    runner.invoke(cli, ['pull', '--reset-hard'])
    assert mock_click_confirm.called
    assert mock_click_confirm.call_args_list[0][1] == {'abort': True}
    assert not mock_pull_issues.called


@mock.patch('jira_offline.entrypoint.Jira')
def test_cli_new_error_when_passed_project_not_in_config(mock_jira_local, mock_jira):
    '''
    Ensure an error happens when the passed --project is missing from config.projects
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['new', 'EGG', 'Story', 'Summary of issue'])
    assert result.exit_code == 1
    assert not mock_jira.new_issue.called


@mock.patch('jira_offline.entrypoint.Jira')
def test_cli_new_error_when_not_passed_epic_name_for_epic(mock_jira_local, mock_jira):
    '''
    Ensure an error happens when --epic-name is not passed for Epic creation
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['new', 'TEST', 'Epic', 'Summary of issue'])
    assert result.exit_code == 1
    assert not mock_jira.new_issue.called


@mock.patch('jira_offline.entrypoint.Jira')
def test_cli_new_error_when_passed_epic_ref_for_epic(mock_jira_local, mock_jira):
    '''
    Ensure an error happens when --epic-ref is passed for Epic creation
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['new', 'TEST', 'Epic', 'Summary of issue', '--epic-ref', 'TEST-1'])
    assert result.exit_code == 1
    assert not mock_jira.new_issue.called


@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint.create_issue')
def test_cli_new_fixversions_param_key_is_passed_to_create_issue_with_case_change(mock_create_issue, mock_jira_local, mock_jira):
    '''
    Ensure the --fixversions param is passed into create_issue() as fixVersions
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['new', 'TEST', 'Story', 'Summary of issue', '--fix-versions', '0.1'])
    assert result.exit_code == 0


@mock.patch('jira_offline.entrypoint.Jira')
def test_cli_new_can_return_json(mock_jira_local, mock_jira):
    '''
    Ensure new command can return output as JSON
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    # add fixture to Jira dict
    mock_jira['issue1'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()
    result = runner.invoke(cli, ['new', '--json', 'TEST', 'Story', 'Summary of issue'])
    assert result.exit_code == 0
    try:
        json.loads(f'{result.output}')
    except json.decoder.JSONDecodeError:
        pytest.fail('Invalid JSON returned!')


@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint._print_table')
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


@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint.lint_fixversions')
def test_cli_lint_fixversions_echo(mock_lint_fixversions, mock_jira_local, mock_jira):
    '''
    Ensure lint fixversions command calls click.echo without error
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['lint', 'fixversions'])
    assert result.exit_code == 0
    assert mock_lint_fixversions.called
    assert result.output.endswith(' issues missing the fixVersions field\n')


@mock.patch('jira_offline.entrypoint.lint_fixversions')
def test_cli_lint_fixversions_fix_requires_words(mock_lint_fixversions):
    '''
    Ensure lint fixversions with --fix param errors without --value
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'fixversions'])
    assert result.exit_code != 0
    assert result.output.endswith('You must pass --value with --fix\n')


@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint.lint_fixversions')
def test_cli_lint_fixversions_fix_passes_words_to_lint_func(mock_lint_fixversions, mock_jira_local, mock_jira):
    '''
    Ensure lint fixversions with --fix and --value correctly calls lint_fixversions
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'fixversions', '--value', '0.1'])
    assert result.exit_code == 0
    mock_lint_fixversions.assert_called_with(mock_jira, fix=True, value='0.1')


@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint.lint_issues_missing_epic')
def test_cli_lint_issues_missing_epic_echo(mock_lint_issues_missing_epic, mock_jira_local, mock_jira):
    '''
    Ensure lint issues_missing_epic command calls click.echo without error
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['lint', 'issues-missing-epic'])
    assert result.exit_code == 0
    assert mock_lint_issues_missing_epic.called
    assert result.output.endswith(' issues missing an epic\n')


@mock.patch('jira_offline.entrypoint.lint_issues_missing_epic')
def test_cli_lint_issues_missing_epic_fix_requires_epic_ref(mock_lint_issues_missing_epic):
    '''
    Ensure lint issues_missing_epic with --fix param errors without --epic-ref
    '''
    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'issues-missing-epic'])
    assert result.exit_code != 0
    assert result.output.endswith('You must pass --epic_ref with --fix\n')


@mock.patch('jira_offline.entrypoint.Jira')
@mock.patch('jira_offline.entrypoint.lint_issues_missing_epic')
def test_cli_lint_issues_missing_epic_fix_passes_epic_ref_to_lint_func(mock_lint_issues_missing_epic, mock_jira_local, mock_jira):
    '''
    Ensure lint issues-missing-epic with --fix and --epic_ref correctly calls lint_issues_missing_epic
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, ['lint', '--fix', 'issues-missing-epic', '--epic-ref', 'TEST'])
    assert result.exit_code == 0
    mock_lint_issues_missing_epic.assert_called_with(mock_jira, fix=True, epic_ref='TEST')

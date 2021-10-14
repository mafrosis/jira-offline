import json
from unittest import mock

import click
from click.testing import CliRunner
import pytest

from fixtures import ISSUE_1, ISSUE_NEW
from jira_offline.cli import cli
from jira_offline.jira import Issue


def test_cli_show__invalid_issue_key(mock_jira):
    '''
    Ensure show command errors when passed an invalid/missing Issue key
    '''
    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        result = runner.invoke(cli, ['show', 'TEST-71'])

    assert result.exit_code == 1, result.output
    assert result.stderr == 'Unknown issue key\nAborted!\n'


@pytest.mark.parametrize('command,params', [
    ('show', ('--json', 'TEST-71')),
    ('new', ('--json', 'TEST', 'Story', 'Summary of issue')),
    ('edit', ('--json', 'TEST-71', '--summary', 'A new summary')),
])
def test_cli_commands_can_return_json(mock_jira, project, command, params):
    '''
    Ensure show command can return output as JSON
    '''
    # add a single lonely fixture to the Jira store
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira), \
            mock.patch('jira_offline.utils.cli.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, [command, *params])

    assert result.exit_code == 0, result.output
    try:
        json.loads(f'{result.stdout}')
    except json.decoder.JSONDecodeError:
        pytest.fail('Invalid JSON returned!')


@mock.patch('jira_offline.cli.main.pull_issues')
def test_cli_pull__reset_flag_calls_confirm_abort(mock_pull_issues, mock_jira):
    '''
    Ensure pull --reset calls click.confirm() with abort=True flag
    '''
    click.confirm = mock_click_confirm = mock.Mock(side_effect=click.exceptions.Abort)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        runner.invoke(cli, ['pull', '--reset'])

    assert mock_click_confirm.called
    assert mock_click_confirm.call_args_list[0][1] == {'abort': True}
    assert not mock_pull_issues.called


def test_cli_new__error_when_passed_project_not_in_config(mock_jira):
    '''
    Ensure an error happens when the passed --project is missing from config.projects
    '''
    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        result = runner.invoke(cli, ['new', 'EGG', 'Story', 'Summary of issue'])

    assert result.exit_code == 1, result.output
    assert not mock_jira.new_issue.called


def test_cli_new__error_when_not_passed_epic_name_for_epic(mock_jira):
    '''
    Ensure an error happens when --epic-name is not passed for Epic creation
    '''
    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        result = runner.invoke(cli, ['new', 'TEST', 'Epic', 'Summary of issue'])

    assert result.exit_code == 1, result.output
    assert not mock_jira.new_issue.called


def test_cli_new__error_when_passed_epic_link_for_epic(mock_jira):
    '''
    Ensure an error happens when --epic-link is passed for Epic creation
    '''
    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        result = runner.invoke(cli, ['new', 'TEST', 'Epic', 'Summary of issue', '--epic-link', 'TEST-1'])

    assert result.exit_code == 1, result.output
    assert not mock_jira.new_issue.called


def test_cli_edit__can_change_an_existing_issue(mock_jira, project):
    '''
    Ensure success when editing an existing issue
    '''
    # add fixture to Jira
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira), \
            mock.patch('jira_offline.utils.cli.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['edit', 'TEST-71', '--summary', 'A new summary'])

    assert result.exit_code == 0, result.output
    assert mock_jira['TEST-71'].summary == 'A new summary'
    assert mock_jira.write_issues.called


def test_cli_edit__can_change_a_new_issue(mock_jira, project):
    '''
    Ensure success when editing a new issue
    '''
    # add new issue fixture to Jira
    mock_jira['7242cc9e-ea52-4e51-bd84-2ced250cabf0'] = Issue.deserialize(ISSUE_NEW, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira), \
            mock.patch('jira_offline.utils.cli.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['edit', '7242cc9e-ea52-4e51-bd84-2ced250cabf0', '--summary', 'A new summary'])

    assert result.exit_code == 0, result.output
    assert mock_jira['7242cc9e-ea52-4e51-bd84-2ced250cabf0'].summary == 'A new summary'
    assert mock_jira.write_issues.called


def test_cli_delete__can_delete_an_issue(mock_jira, project):
    '''
    Ensure success when deleting a new issue
    '''
    # Add fixture to Jira
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira), \
            mock.patch('jira_offline.utils.cli.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['delete', 'TEST-71'])

    assert result.exit_code == 0, result.output
    assert 'TEST-71' not in mock_jira
    assert mock_jira.write_issues.called


@mock.patch('jira_offline.cli.main.write_default_user_config')
def test_cli_config__config_path_used_when_config_param_supplied(mock_write_default_user_config):
    '''
    Ensure path supplied in --config is passed into `write_default_user_config`
    '''
    result = CliRunner(mix_stderr=False).invoke(cli, ['config', '--config', '/tmp/egg.ini'])

    assert result.exit_code == 0, result.output
    mock_write_default_user_config.assert_called_with('/tmp/egg.ini')


@mock.patch('jira_offline.cli.main.write_default_user_config')
@mock.patch('jira_offline.cli.main.get_default_user_config_filepath')
def test_cli_config__default_config_path_used_when_config_param_not_supplied(
        mock_get_default_user_config_filepath, mock_write_default_user_config
    ):
    '''
    Ensure default config path is used when --config is not supplied
    '''
    mock_get_default_user_config_filepath.return_value = '/tmp/bacon.ini'

    result = CliRunner(mix_stderr=False).invoke(cli, ['config'])

    assert result.exit_code == 0, result.output
    mock_write_default_user_config.assert_called_with('/tmp/bacon.ini')

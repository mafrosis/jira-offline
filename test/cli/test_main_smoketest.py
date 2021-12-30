'''
Two dumb smoke tests to check for errors via calling the application CLI with standard parameters.
Failures here often uncover untested parts of the codebase.

One test for when the issue cache is empty, and one test for when there is a single issue.
'''
from unittest import mock

from click.testing import CliRunner
import pytest

from fixtures import ISSUE_1
from jira_offline.cli import cli
from jira_offline.jira import Issue


# 0: CLI command name
# 1: tuple of "basic" parameters to pass
# 2: expected return code when Jira dict is empty (used in test_cli_smoketest_empty)
CLI_COMMAND_MAPPING = [
    (('config',), tuple(), 0),
    (('project', 'list'), tuple(), 0),
    (('project', 'delete'), ('--force', 'TEST',), 0),
    (('project', 'update-auth'), ('TEST',), 0),
    (('ls',), tuple(), 1),
    (('show',), ('TEST-71',), 1),
    (('diff',), ('TEST-71',), 1),
    (('reset',), ('TEST-71',), 1),
    (('reset',), ('all', '--force'), 0),
    (('clone',), ('https://jira.atlassian.com/TEST1',), 0),
    (('new',), ('TEST', 'Story', 'Summary'), 1),
    (('pull',), tuple(), 0),
    (('push',), tuple(), 1),
    (('edit',), ('TEST-71', '--summary', 'Egg'), 1),
    (('delete',), ('TEST-71',), 1),
    (('completion',), ('bash','--stdout'), 0),
    (('export',), ('/tmp',), 0),
]


@pytest.mark.parametrize('command,params,_', CLI_COMMAND_MAPPING)
@mock.patch('jira_offline.cli.main.create_issue')
@mock.patch('jira_offline.cli.main.pull_single_project')
@mock.patch('jira_offline.cli.main.pull_issues')
@mock.patch('jira_offline.cli.main.push_issues')
@mock.patch('jira_offline.cli.main.authenticate')
@mock.patch('jira_offline.cli.project.authenticate')
@mock.patch('jira_offline.cli.main.write_default_user_config')
def test_main_smoketest(mock_write_config, mock_auth1, mock_auth2, mock_push_issues, mock_pull_issues,
                        mock_pull_single_project, mock_create_issue, mock_jira, project, command, params, _):
    '''
    Test when the jira-offline issue cache has a single issue
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira), \
            mock.patch('jira_offline.cli.project.jira', mock_jira), \
            mock.patch('jira_offline.cli.utils.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, [*command, *params])

    # CLI should always exit zero
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize('command,params,exit_code', CLI_COMMAND_MAPPING)
@mock.patch('jira_offline.cli.main.create_issue')
@mock.patch('jira_offline.cli.main.pull_single_project')
@mock.patch('jira_offline.cli.main.pull_issues')
@mock.patch('jira_offline.cli.main.push_issues')
@mock.patch('jira_offline.cli.main.authenticate')
@mock.patch('jira_offline.cli.project.authenticate')
@mock.patch('jira_offline.cli.main.write_default_user_config')
def test_main_smoketest_empty(mock_write_config, mock_auth1, mock_auth2, mock_push_issues, mock_pull_issues,
                              mock_pull_single_project, mock_create_issue, mock_jira, command,
                              params, exit_code):
    '''
    Test when the jira-offline issue cache is empty
    '''
    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.main.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.cli.project.jira', mock_jira):
        result = runner.invoke(cli, [*command, *params])

    # some CLI commands will exit with error, others will not..
    assert result.exit_code == exit_code, result.stdout

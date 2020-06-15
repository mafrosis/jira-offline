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
from jira_offline.main import Issue


# 0: CLI command name
# 1: tuple of "basic" parameters to pass
# 2: expected return code when Jira dict is empty (used in test_cli_smoketest_empty)
CLI_COMMAND_MAPPING = [
    ('projects', tuple(), 0),
    ('ls', tuple(), 1),
    ('show', ('issue1',), 1),
    ('diff', ('issue1',), 1),
    ('reset', ('issue1',), 1),
    ('clone', ('https://jira.atlassian.com/TEST1',), 0),
    ('new', ('TEST', 'Story', 'Summary'), 0),
    ('pull', tuple(), 0),
    ('push', tuple(), 1),
    ('edit', ('issue1', '--summary', 'Egg'), 1),
]


@pytest.mark.parametrize('command,params,_', CLI_COMMAND_MAPPING)
@mock.patch('jira_offline.cli.Jira')
@mock.patch('jira_offline.cli.main.create_issue')
@mock.patch('jira_offline.cli.main.pull_single_project')
@mock.patch('jira_offline.cli.main.pull_issues')
@mock.patch('jira_offline.cli.main.push_issues')
@mock.patch('jira_offline.cli.main.authenticate')
def test_main_smoketest(mock_authenticate, mock_push_issues, mock_pull_issues,
                        mock_pull_single_project, mock_create_issue,
                        mock_jira_local, mock_jira, command, params, _):
    '''
    Test when the jira-offline issue cache has a single issue
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
@mock.patch('jira_offline.cli.Jira')
@mock.patch('jira_offline.cli.main.create_issue')
@mock.patch('jira_offline.cli.main.pull_single_project')
@mock.patch('jira_offline.cli.main.pull_issues')
@mock.patch('jira_offline.cli.main.push_issues')
@mock.patch('jira_offline.cli.main.authenticate')
def test_main_smoketest_empty(mock_authenticate, mock_push_issues, mock_pull_issues,
                              mock_pull_single_project, mock_create_issue,  mock_jira_local,
                              mock_jira, command, params, exit_code):
    '''
    Test when the jira-offline issue cache is empty
    '''
    # set function-local instance of Jira class to our test mock
    mock_jira_local.return_value = mock_jira

    runner = CliRunner()
    result = runner.invoke(cli, [command, *params])
    # some CLI commands will exit with error, others will not..
    assert result.exit_code == exit_code

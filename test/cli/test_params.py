import logging
from unittest import mock

from click.testing import CliRunner

from fixtures import ISSUE_1
from jira_offline.cli import cli
from jira_offline.jira import Issue



def test_cli__global_options__verbose_flag_sets_logger_to_info_level(mock_jira):
    '''
    Ensure the --verbose flag correctly sets the logger level
    '''
    runner = CliRunner()

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        runner.invoke(cli, ['--verbose', 'ls'])

    assert logging.getLogger('jira').level == logging.INFO


def test_cli__global_options__debug_flag_sets_logger_to_debug_level(mock_jira):
    '''
    Ensure the --debug flag correctly sets the logger level
    '''
    runner = CliRunner()

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        runner.invoke(cli, ['--debug', 'ls'])

    assert logging.getLogger('jira').level == logging.DEBUG


def test_cli__filter_options__filter_flag_sets_jira_object_filter(mock_jira):
    '''
    Ensure the --filter flag is set into jira.filter
    '''
    # add a single lonely fixture to the Jira store
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    runner = CliRunner()

    with mock.patch('jira_offline.cli.main.jira', mock_jira), \
            mock.patch('jira_offline.cli.params.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):

        result = runner.invoke(cli, ['ls', '--filter', "project == TEST"])

    assert result.exit_code == 0, result.stdout
    assert mock_jira.filter._where is not None

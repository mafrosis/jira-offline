import logging
from unittest import mock

from click.testing import CliRunner

from jira_offline.cli import cli


def test_cli__verbose_flag_sets_logger_to_info_level(mock_jira):
    '''
    Ensure the --verbose flag correctly sets the logger level
    '''
    runner = CliRunner()

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        runner.invoke(cli, ['--verbose', 'show'])

    assert logging.getLogger('jira').level == logging.INFO


def test_cli__debug_flag_sets_logger_to_debug_level(mock_jira):
    '''
    Ensure the --debug flag correctly sets the logger level
    '''
    runner = CliRunner()

    with mock.patch('jira_offline.cli.main.jira', mock_jira):
        runner.invoke(cli, ['--debug', 'show'])

    assert logging.getLogger('jira').level == logging.DEBUG

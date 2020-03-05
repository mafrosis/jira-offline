from unittest import mock

import pytest

from jira_cli.auth import authenticate, get_user_creds
from jira_cli.exceptions import FailedAuthError
from jira_cli.models import AppConfig


@mock.patch('jira_cli.auth.get_user_creds')
@mock.patch('jira_cli.auth._test_jira_connect')
@mock.patch('jira_cli.auth.click')
def test_authenticate__calls_get_user_creds_when_username_passed(mock_click, mock_test_jira_connect, mock_get_user_creds):
    '''
    Ensure get_user_creds() is called when params passed
    '''
    app_config = AppConfig()
    app_config.write_to_disk = mock.Mock()

    authenticate(app_config, 'http', 'example.com', username='egg')

    mock_get_user_creds.assert_called_with(app_config, 'egg')
    assert app_config.write_to_disk.called


@mock.patch('jira_cli.auth.get_user_creds')
def test_authenticate__doesnt_write_config_when_get_user_creds_raises(mock_get_user_creds):
    '''
    Ensure config.write_to_disk() is not called when get_user_creds() raises exception
    '''
    app_config = AppConfig()
    app_config.write_to_disk = mock.Mock()

    # mock get_user_creds() to fail
    mock_get_user_creds.side_effect = FailedAuthError

    with pytest.raises(FailedAuthError):
        authenticate(app_config, 'http', 'example.com', username='egg')

    assert not app_config.write_to_disk.called


@pytest.mark.parametrize('app_config', [
    AppConfig(),
    AppConfig(username='test', password='dummy', projects={'TEST': None}),
])
@mock.patch('jira_cli.auth._test_jira_connect')
@mock.patch('jira_cli.auth.click')
def test_get_user_creds__calls_click_prompt_and_jira_connect(mock_click, mock_test_jira_connect, app_config):
    '''
    Ensure that get_user_creds() makes calls to click.prompt and Jira.connect()
    '''
    # mock return from user CLI prompts
    mock_click.prompt.return_value = 'egg'

    # mock AppConfig.write_to_disk calls
    app_config.write_to_disk = mock.Mock()

    get_user_creds(app_config)

    assert mock_click.prompt.call_count == 2
    assert app_config.username == 'egg'
    assert app_config.password == 'egg'
    assert mock_test_jira_connect.called


@mock.patch('jira_cli.auth._test_jira_connect')
@mock.patch('jira_cli.auth.click')
def test_get_user_creds__calls_prompt_only_once_when_username_passed(mock_click, mock_test_jira_connect):
    '''
    Ensure that get_user_creds() only calls click.prompt once when username param is passed
    '''
    app_config = AppConfig()

    # mock return from user CLI prompts
    mock_click.prompt.return_value = 'egg'

    # mock AppConfig.write_to_disk calls
    app_config.write_to_disk = mock.Mock()

    get_user_creds(app_config, username='bacon')

    assert mock_click.prompt.call_count == 1
    assert app_config.username == 'bacon'
    assert app_config.password == 'egg'

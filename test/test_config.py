from unittest import mock

import requests
import pytest

from jira_cli.config import AppConfig, load_config, _get_user_creds


@pytest.mark.parametrize('config_property,value', [
    ('username', 'test'),
    ('password', 'egg'),
    ('hostname', 'jira'),
    ('last_updated', 2019),
])
@mock.patch('jira_cli.config.json')
@mock.patch('jira_cli.config.os')
@mock.patch('jira_cli.config.sys')
@mock.patch('builtins.open')
def test_load_config__config_file_exists(mock_open, mock_sys, mock_os, mock_json, config_property, value):
    '''
    Test existing config file loads correctly into dataclass AppConfig
    '''
    # config file already exists
    mock_os.path.exists.return_value = True
    mock_json.load.return_value = {config_property: value}

    conf = load_config()

    assert mock_open.called
    assert mock_json.load.called
    assert isinstance(conf, AppConfig)
    assert getattr(conf, config_property) == value


@mock.patch('jira_cli.config.AppConfig')
@mock.patch('jira_cli.config._get_user_creds')
@mock.patch('jira_cli.config.os')
@mock.patch('jira_cli.config.sys')
@mock.patch('jira_cli.config.click')
def test_load_config__no_config_file_exists(mock_click, mock_sys, mock_os, mock_get_user_creds, mock_appconfig_class):
    '''
    Test that when no config file exists, an AppConfig object is created and _get_user_creds is called
    '''
    # config file does not exist
    mock_os.path.exists.return_value = False

    load_config()

    assert mock_appconfig_class.called  # class instantiated
    assert mock_get_user_creds.called


@mock.patch('jira_cli.config.AppConfig')
@mock.patch('jira_cli.config._get_user_creds')
@mock.patch('jira_cli.config.os')
def test_load_config__no_config_file_missing_causes_call_to_get_user_creds(mock_os, mock_get_user_creds, mock_appconfig_class):
    '''
    Ensure a missing config file causes a constructor call on AppConfig and a call to _get_user_creds()
    '''
    # config file NOT exist
    mock_os.path.exists.return_value = False

    load_config(prompt_for_creds=True)

    assert mock_appconfig_class.called
    assert mock_get_user_creds.called


@mock.patch('jira_cli.config.AppConfig')
@mock.patch('jira_cli.config._get_user_creds')
@mock.patch('jira_cli.config.json')
@mock.patch('jira_cli.config.os')
@mock.patch('builtins.open')
def test_load_config__existing_creds_skips_call_to_get_user_creds(mock_open, mock_os, mock_json, mock_get_user_creds, mock_appconfig_class):
    '''
    Ensure that when creds are already configured there is no call to _get_user_creds()
    '''
    # config file already exists
    mock_os.path.exists.return_value = True
    mock_json.load.return_value = {}
    mock_appconfig_class.return_value.deserialize.return_value = AppConfig()

    load_config(prompt_for_creds=False)

    assert not mock_appconfig_class.called
    assert not mock_get_user_creds.called


@mock.patch('jira_cli.config.AppConfig')
@mock.patch('jira_cli.config._get_user_creds')
@mock.patch('jira_cli.config.os')
def test_load_config__prompt_for_creds_param_causes_call_to_get_user_creds(mock_os, mock_get_user_creds, mock_appconfig_class):
    '''
    Ensure that passing the prompt_for_creds param causes a call to _get_user_creds()
    '''
    # config file doesn't exist
    mock_os.path.exists.return_value = False

    load_config(prompt_for_creds=True)

    assert mock_get_user_creds.called


@pytest.mark.parametrize('app_config', [
    AppConfig(),
    AppConfig(username='test', password='dummy', projects={'TEST': None}),
])
@mock.patch('jira_cli.config._test_jira_connect')
@mock.patch('jira_cli.config.click')
def test_get_user_creds__calls_click_prompt_and_jira_connect(mock_click, mock_test_jira_connect, app_config):
    '''
    Ensure that _get_user_creds() makes calls to click.prompt and Jira.connect()
    '''
    # mock return from user CLI prompts
    mock_click.prompt.return_value = 'egg'

    # mock AppConfig.write_to_disk calls
    app_config.write_to_disk = mock.Mock()

    _get_user_creds(app_config)

    assert mock_click.prompt.call_count == 2
    assert app_config.username == 'egg'
    assert app_config.password == 'egg'
    assert mock_test_jira_connect.called


@mock.patch('jira_cli.config._test_jira_connect')
@mock.patch('jira_cli.config.os')
@mock.patch('jira_cli.config.sys')
@mock.patch('jira_cli.config.click')
def test_get_user_creds__bad_credentials_dont_write_config_and_hostname_set_none(mock_click, mock_sys, mock_os, mock_test_jira_connect):
    '''
    Test that when _test_jira_connect() returns false, the config file is NOT written and hostname
    is set to None
    '''
    # set an empty AppConfig
    app_config = AppConfig(hostname='example.com')

    # mock AppConfig.write_to_disk calls
    app_config.write_to_disk = mock.Mock()

    # mock Jira.connect to fail
    mock_test_jira_connect.return_value = False

    _get_user_creds(app_config)

    assert mock_click.prompt.call_count == 2
    assert mock_test_jira_connect.called
    assert not app_config.write_to_disk.called
    assert app_config.hostname is None

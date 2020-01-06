from unittest import mock

import requests
import pytest

from jira_cli.config import AppConfig, load_config

# pylint: disable=unused-argument,protected-access


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
    """
    Test existing config file loads correctly into dataclass AppConfig
    """
    # config file already exists
    mock_os.path.exists.return_value = True
    mock_json.load.return_value = {config_property: value}

    conf = load_config()

    assert mock_open.called
    assert mock_json.load.called
    assert isinstance(conf, AppConfig)
    assert getattr(conf, config_property) == value


@mock.patch('jira_cli.config.AppConfig')
@mock.patch('jira_cli.config.Jira')
@mock.patch('jira_cli.config.os')
@mock.patch('jira_cli.config.sys')
@mock.patch('jira_cli.config.click')
def test_load_config__not_config_file_exists_input_ok(mock_click, mock_sys, mock_os, mock_jira_class, mock_appconfig_class):
    """
    Test no config file exists triggers:
        - input calls
        - successful Jira.connect
        - file write
    """
    # config file does not exist
    mock_os.path.exists.return_value = False
    mock_click.prompt.side_effect = ['test', 'egg']

    conf = load_config()

    assert mock_click.prompt.call_count == 2
    assert mock_jira_class.called  # class instantiated
    assert mock_jira_class.return_value._connect.called
    assert mock_appconfig_class.called  # class instantiated
    assert mock_appconfig_class.return_value.write_to_disk.called
    assert conf.username == 'test'
    assert conf.password == 'egg'


@mock.patch('jira_cli.config.AppConfig')
@mock.patch('jira_cli.config.Jira')
@mock.patch('jira_cli.config.os')
@mock.patch('jira_cli.config.sys')
@mock.patch('jira_cli.config.click')
def test_load_config__not_config_file_exists_input_bad(mock_click, mock_sys, mock_os, mock_jira_class, mock_appconfig_class):
    """
    Test no config file exists triggers:
        - input calls
        - FAILED Jira.connect
        - NO file write
    """
    # config file does not exist
    mock_os.path.exists.return_value = False
    mock_click.prompt.side_effect = ['test', 'badpassword']

    # Jira._connect to fail
    mock_jira_class.return_value._connect.side_effect = requests.exceptions.ConnectionError

    conf = load_config()

    assert mock_click.prompt.call_count == 2
    assert mock_jira_class.called  # class instantiated
    assert mock_jira_class.return_value._connect.called
    assert mock_appconfig_class.called  # class instantiated
    assert not mock_appconfig_class.return_value.write_to_disk.called
    assert conf.hostname is None


@mock.patch('jira_cli.config.json')
@mock.patch('jira_cli.config.os')
@mock.patch('jira_cli.config.sys')
@mock.patch('builtins.open')
def test_load_config__projects_arg_extends_projects_config(mock_open, mock_sys, mock_os, mock_json):
    """
    Ensure project IDs passed with --projects param on CLI are merged into the existing
    config.projects set
    """
    # config file already exists
    mock_os.path.exists.return_value = True

    # projects field is serialized as list type (for JSON-compatibility)
    mock_json.load.return_value = {'projects': ['CNTS']}

    # pass new project as set type
    conf = load_config({'EGG'})

    assert conf.projects == {'CNTS', 'EGG'}

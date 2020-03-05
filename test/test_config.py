from unittest import mock

import pytest

from jira_cli.config import load_config
from jira_cli.models import AppConfig


@pytest.mark.parametrize('config_property,value', [
    ('username', 'test'),
    ('password', 'egg'),
    ('hostname', 'jira'),
    ('last_updated', 2019),
])
@mock.patch('jira_cli.config.json')
@mock.patch('jira_cli.config.os')
@mock.patch('builtins.open')
def test_load_config__config_file_exists(mock_open, mock_os, mock_json, config_property, value):
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
@mock.patch('jira_cli.config.os')
@mock.patch('jira_cli.config.click')
def test_load_config__config_created_when_no_config_file_exists(mock_click, mock_os, mock_appconfig_class):
    '''
    Test that when no config file exists, an AppConfig object is created
    '''
    # config file does not exist
    mock_os.path.exists.return_value = False

    load_config()

    assert mock_appconfig_class.called  # class instantiated

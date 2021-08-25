import os
from unittest import mock

from jira_offline.config import get_default_user_config_filepath, load_config
from jira_offline.models import AppConfig


@mock.patch('jira_offline.config.load_user_config')
@mock.patch('jira_offline.config.AppConfig')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
def test_load_config__app_config_created_when_no_config_file_exists(mock_click, mock_os,
                                                                    mock_appconfig_class,
                                                                    mock_load_user_config):
    '''
    Test that when no app config file exists, an AppConfig object is created
    '''
    # App config file does not exist
    mock_os.path.exists.return_value = False

    load_config()

    assert mock_appconfig_class.called  # class instantiated


@mock.patch('jira_offline.config.load_user_config')
@mock.patch('jira_offline.config.AppConfig')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
def test_load_config__calls_load_user_config(mock_click, mock_os, mock_appconfig_class,
                                             mock_load_user_config):
    '''
    Test that when no config file exists, an AppConfig object is created
    '''
    # App config file does not exist as it does not affect the test result, and this obviates the
    # need to mock builtins.open
    mock_os.path.exists.return_value = False

    load_config()

    assert mock_load_user_config.called


@mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': '/tmp/egg'})
def test_get_default_user_config_filepath_1():
    '''
    Check XDG_CONFIG_HOME env variable is respected
    '''
    path = get_default_user_config_filepath()

    assert path == '/tmp/egg/jira-offline/jira-offline.ini'


def test_get_default_user_config_filepath_2():
    '''
    Check default path is returned when XDG_CONFIG_HOME is unset
    '''
    path = get_default_user_config_filepath()

    assert path == '/root/.config/jira-offline/jira-offline.ini'


@mock.patch('jira_offline.config.load_user_config')
@mock.patch('jira_offline.config.upgrade_schema')
@mock.patch('jira_offline.config.AppConfig', autospec=AppConfig)
@mock.patch('jira_offline.config.json')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
@mock.patch('builtins.open')
def test_load_config__upgrade_called_when_version_changes(mock_open, mock_click, mock_os, mock_json,
                                                          mock_appconfig_class, mock_upgrade_schema,
                                                          mock_load_user_config):
    '''
    Ensure the schema upgrade function is called when app.config schema version has changed
    '''
    # config file exists
    mock_os.path.exists.return_value = True

    # mock AppConfig constructor and AppConfig.deserialize to return an AppConfig object
    mock_appconfig_class.return_value = mock_appconfig_class.deserialize.return_value = AppConfig()

    # mock config existing file to have schema_version==1
    mock_json.load.return_value = {
        'schema_version': 1,
        'projects': {
            '09004155d6268ca91d0150a2d6c73c712926743c': {'key': 'TEST', 'name': 'TEST'}
        }
    }

    # ensure config.write_to_disk is not called
    mock_upgrade_schema.return_value = False

    config = load_config()

    assert mock_upgrade_schema.called
    assert config.schema_version == AppConfig().schema_version

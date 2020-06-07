from unittest import mock

from jira_offline.config import load_config, upgrade_schema
from jira_offline.models import AppConfig


@mock.patch('jira_offline.config.AppConfig')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
def test_load_config__config_created_when_no_config_file_exists(mock_click, mock_os, mock_appconfig_class):
    '''
    Test that when no config file exists, an AppConfig object is created
    '''
    # config file does not exist
    mock_os.path.exists.return_value = False

    load_config()

    assert mock_appconfig_class.called  # class instantiated


@mock.patch('jira_offline.config.upgrade_schema')
@mock.patch('jira_offline.config.AppConfig')
@mock.patch('jira_offline.config.json')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
@mock.patch('builtins.open')
def test_load_config__upgrade_called_when_version_changes(mock_open, mock_click, mock_os, mock_json,
                                                          mock_appconfig_class, mock_upgrade_schema):
    '''
    Ensure the schema upgrade function is called when app.config schema version has changed
    '''
    # config file exists
    mock_os.path.exists.return_value = True

    # mock AppConfig constgructor to return version == 2
    mock_appconfig_class.return_value = AppConfig(schema_version=2)

    # mock config existing file to be scheme version == 1
    mock_json.load.return_value = {
        'schema_version': 1,
        'projects': {
            '09004155d6268ca91d0150a2d6c73c712926743c': {'key': 'TEST', 'name': 'TEST'}
        }
    }

    config = load_config()

    assert mock_upgrade_schema.called
    assert config.schema_version == 2


@mock.patch('jira_offline.config.config_upgrade_1_to_2')
def test_upgrade_schema__calls_correct_upgrade_func(mock_upgrade_func):
    '''
    Ensure the correct upgrade function is called based on the versions

    This is intentionally _not_ testing the upgrade code itself, just the calling mechanism
    '''
    config_json = {
        'schema_version': 1,
        'projects': {
            '09004155d6268ca91d0150a2d6c73c712926743c': {'key': 'TEST', 'name': 'TEST'}
        }
    }

    upgrade_schema(config_json, 1, 2)

    assert mock_upgrade_func.called

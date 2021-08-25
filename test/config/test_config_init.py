import os
from unittest import mock

from jira_offline.config import (apply_user_config_to_projects, get_default_user_config_filepath,
                                 load_config)
from jira_offline.models import AppConfig, ProjectMeta


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


@mock.patch('jira_offline.config.apply_user_config_to_projects')
@mock.patch('jira_offline.config.load_user_config')
@mock.patch('jira_offline.config.AppConfig')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
def test_load_config__calls_load_user_config(mock_click, mock_os, mock_appconfig_class,
                                             mock_load_user_config, mock_apply_user_config_to_projects):
    '''
    Test load_config does indeed call load_user_config and apply_user_config_to_projects
    '''
    # App config file does not exist as it does not affect the test result, and this obviates the
    # need to mock builtins.open
    mock_os.path.exists.return_value = False

    load_config()

    assert mock_load_user_config.called
    assert mock_apply_user_config_to_projects.called


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


@mock.patch('jira_offline.config.apply_user_config_to_projects')
@mock.patch('jira_offline.config.load_user_config')
@mock.patch('jira_offline.config.upgrade_schema')
@mock.patch('jira_offline.config.AppConfig', autospec=AppConfig)
@mock.patch('jira_offline.config.json')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
@mock.patch('builtins.open')
def test_load_config__upgrade_called_when_version_changes(
        mock_open, mock_click, mock_os, mock_json, mock_appconfig_class, mock_upgrade_schema,
        mock_load_user_config, mock_apply_user_config_to_projects
    ):
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


@mock.patch('jira_offline.config.apply_default_reporter')
@mock.patch('jira_offline.config.hashlib')
@mock.patch('jira_offline.config.os')
@mock.patch('builtins.open')
def test_apply_user_config_to_projects__does_not_apply_when_config_hash_unchanged(
        mock_open, mock_os, mock_hashlib, mock_apply_default_reporter, project
    ):
    '''
    Ensure the apply function is NOT called when the hashes match
    '''
    # Create config test fixture
    config = AppConfig(user_config_hash='abcdef1234567890')
    config.projects[project.id] = project

    # Config file exists
    mock_os.path.exists.return_value = True

    mock_hashlib.sha1.return_value.hexdigest.return_value = 'abcdef1234567890'

    apply_user_config_to_projects(config)

    assert mock_apply_default_reporter.called is False


@mock.patch('jira_offline.config.apply_default_reporter')
@mock.patch('jira_offline.config.hashlib')
@mock.patch('jira_offline.config.os')
@mock.patch('builtins.open')
def test_apply_user_config_to_projects__applies_when_config_hash_is_changed(
        mock_open, mock_os, mock_hashlib, mock_apply_default_reporter, project
    ):
    '''
    Ensure the apply function is called when the hashes are different
    '''
    # Create config test fixture
    config = AppConfig(user_config_hash='abcdef1234567890')
    config.projects[project.id] = project

    # Config file exists
    mock_os.path.exists.return_value = True

    mock_hashlib.sha1.return_value.hexdigest.return_value = 'aaaaaaaaaaaaaaaa'

    apply_user_config_to_projects(config)

    assert mock_apply_default_reporter.called is True


@mock.patch('jira_offline.config.apply_default_reporter')
@mock.patch('jira_offline.config.hashlib')
@mock.patch('jira_offline.config.os')
@mock.patch('builtins.open')
def test_apply_user_config_to_projects__apply_function_is_called_once_for_each_project(
        mock_open, mock_os, mock_hashlib, mock_apply_default_reporter, project
    ):
    '''
    Ensure the apply function is called when the hashes are different
    '''
    # Create config test fixture
    config = AppConfig(user_config_hash='abcdef1234567890')
    config.projects[project.id] = project
    config.projects['TEST2'] = ProjectMeta('TEST2')

    # Config file exists
    mock_os.path.exists.return_value = True

    mock_hashlib.sha1.return_value.hexdigest.return_value = 'aaaaaaaaaaaaaaaa'

    apply_user_config_to_projects(config)

    assert mock_apply_default_reporter.call_count == 2

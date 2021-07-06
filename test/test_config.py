from dataclasses import dataclass
import datetime
import os
from typing import Dict, Optional, Set
from unittest import mock

from jira_offline.config import (get_default_user_config_filepath, load_config, upgrade_schema,
                                 write_default_user_config)
from jira_offline.models import AppConfig
from jira_offline.utils.serializer import DataclassSerializer


@mock.patch('jira_offline.config._load_user_config')
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


@mock.patch('jira_offline.config._load_user_config')
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


@mock.patch('jira_offline.config._load_user_config')
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


def test_write_default_user_config(tmpdir):
    '''
    Ensure the default config is written to disk without error
    '''
    write_default_user_config(os.path.join(tmpdir, 'jira-offline.ini'))


#################
# Redefinition of the classes in models.py, when AppConfig.schema_version == 2
#
# Subsequent test compares these classes to the those in models.py to ensure that schema_version is
# incremented on release.
#
@dataclass
class CustomFields_v2(DataclassSerializer):
    epic_ref: Optional[str]
    epic_name: Optional[str]
    estimate: Optional[str]
    acceptance_criteria: Optional[str]

@dataclass
class IssueType_v2(DataclassSerializer):
    name: str
    statuses: Set[str]

@dataclass
class OAuth_v2(DataclassSerializer):
    access_token: Optional[str]
    access_token_secret: Optional[str]
    consumer_key: Optional[str]
    key_cert: Optional[str]

@dataclass  # pylint: disable=too-many-instance-attributes
class ProjectMeta_v2(DataclassSerializer):  # pylint: disable=too-many-instance-attributes
    key: str
    name: Optional[str]
    username: Optional[str]
    password: Optional[str]
    protocol: Optional[str]
    hostname: Optional[str]
    last_updated: Optional[str]
    issuetypes: Dict[str, IssueType_v2]
    custom_fields: CustomFields_v2
    priorities: Optional[Set[str]]
    components: Optional[Set[str]]
    oauth: Optional[OAuth_v2]
    ca_cert: Optional[str]
    timezone: datetime.tzinfo
    config: Optional['AppConfig']

@dataclass
class AppConfig_v2(DataclassSerializer):
    schema_version: int
    user_config_filepath: str
    projects: Dict[str, ProjectMeta_v2]

    sync: AppConfig.Sync

    display: AppConfig.Display
#
#################


def test_appconfig_model__validate_schema_version():
    '''
    Validate that the current AppConfig model has not changed from the v2 schema defined above.

    If this test fails, do the following:

      1. Bump the AppConfig.schema_version default value
      2. Write an upgrade function for app config in config.py
      3. Update the above data model to match the new schema
    '''
    assert AppConfig.schema['properties'] == AppConfig_v2.schema['properties'], \
            'Current AppConfig schema does not match schema_version = 2'

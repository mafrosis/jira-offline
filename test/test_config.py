from dataclasses import dataclass
import datetime
import os
from typing import Dict, Optional, Set
from unittest import mock

import pytest

from jira_offline.config import (_load_user_config, get_default_user_config_filepath, load_config,
                                 upgrade_schema, write_default_user_config)
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


@mock.patch('jira_offline.config.os')
def test_load_user_config__handles_comma_separated_list(mock_os):
    '''
    Ensure comma-separated list is parsed into a python list type
    '''
    # config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = '''
    [display]
    ls = status,summary
    '''

    config = AppConfig()

    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        _load_user_config(config)

    assert config.display.ls_fields == ['status', 'summary']



@mock.patch('jira_offline.config.os')
def test_load_user_config__sync_handles_integer_page_size(mock_os):
    '''
    Config option sync.page-size must be supplied as an integer
    '''
    # config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = '''
    [sync]
    page-size = 99
    '''

    config = AppConfig()

    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        _load_user_config(config)

    assert config.sync.page_size == 99


@mock.patch('jira_offline.config.os')
def test_load_user_config__sync_ignores_non_integer_page_size(mock_os):
    '''
    Config option sync.page-size must be supplied as an integer
    '''
    # config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = '''
    [sync]
    page-size = abc
    '''

    config = AppConfig()

    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        _load_user_config(config)

    assert config.sync.page_size == 25


@pytest.mark.parametrize('customfield_name', [
    ('story-points'),
    ('parent-link'),
])
@mock.patch('jira_offline.config.os')
def test_load_user_config__customfields_handles_firstclass_issue_attributes(mock_os, customfield_name):
    '''
    Some optional user-defined customfields are defined first-class attributes on the Issue model.
    They have slightly different handling.
    '''
    # Config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = f'''
    [customfields]
    {customfield_name} = customfield_10102
    '''

    config = AppConfig()

    # Mock return from open() to return the config.ini fixture
    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        _load_user_config(config)

    assert config.customfields['*'][customfield_name.replace('-', '_')] == 'customfield_10102'


@mock.patch('jira_offline.config.os')
def test_load_user_config__customfields_ignore_reserved_keyword(mock_os):
    '''
    User-defined customfields must not be named using an Issue attribute keyword
    '''
    # Config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = '''
    [customfields]
    priority = customfield_10101
    '''

    config = AppConfig()

    # Mock return from open() to return the config.ini fixture
    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        _load_user_config(config)

    assert 'priority' not in config.customfields


@pytest.mark.parametrize('customfield_value', [
    ('customfield1'),
    ('customfield_xxx'),
    ('10101'),
    (''),
])
@mock.patch('jira_offline.config.os')
def test_load_user_config__customfields_ignore_invalid(mock_os, customfield_value):
    '''
    User-defined customfields must be configured using the correct format
    '''
    # Config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = f'''
    [customfields]
    story-points = {customfield_value}
    '''

    config = AppConfig()

    # Mock return from open() to return the config.ini fixture
    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        _load_user_config(config)

    assert 'story_points' not in config.customfields


@mock.patch('jira_offline.config.os')
def test_load_user_config__customfields_handles_general_and_host_specific(mock_os):
    '''
    Ensure overriding user-defined customfield set per-Jira host is loaded correctly
    '''
    # Config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = '''
    [customfields]
    arbitrary = customfield_10144

    [customfields jira.example.com]
    arbitrary = customfield_10155
    '''

    config = AppConfig()

    # Mock return from open() to return the config.ini fixture
    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        _load_user_config(config)

    assert 'arbitrary' not in config.customfields
    assert config.customfields['*']['arbitrary'] == 'customfield_10144'
    assert config.customfields['jira.example.com']['arbitrary'] == 'customfield_10155'


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
class CustomFields_v3(DataclassSerializer):
    epic_link: Optional[str]
    epic_name: Optional[str]
    sprint: Optional[str]
    story_points: Optional[str]
    parent_link: Optional[str]
    extended: Optional[Dict[str, str]]

@dataclass
class IssueType_v3(DataclassSerializer):
    name: str
    statuses: Set[str]

@dataclass
class OAuth_v3(DataclassSerializer):
    access_token: Optional[str]
    access_token_secret: Optional[str]
    consumer_key: Optional[str]
    key_cert: Optional[str]

@dataclass  # pylint: disable=too-many-instance-attributes
class ProjectMeta_v3(DataclassSerializer):  # pylint: disable=too-many-instance-attributes
    key: str
    name: Optional[str]
    username: Optional[str]
    password: Optional[str]
    protocol: Optional[str]
    hostname: Optional[str]
    last_updated: Optional[str]
    issuetypes: Dict[str, IssueType_v3]
    customfields: Optional[CustomFields_v3]
    priorities: Optional[Set[str]]
    components: Optional[Set[str]]
    oauth: Optional[OAuth_v3]
    ca_cert: Optional[str]
    timezone: datetime.tzinfo
    jira_id: Optional[str]
    config: Optional['AppConfig']

@dataclass
class AppConfig_v3(DataclassSerializer):
    schema_version: int
    user_config_filepath: str
    projects: Dict[str, ProjectMeta_v3]
    sync: AppConfig.Sync
    display: AppConfig.Display
    customfields: Dict[str, dict]
#
#################


def test_appconfig_model__validate_schema_version():
    '''
    Validate that the current AppConfig model has not changed from the v3 schema defined above.

    If this test fails, do the following:

      1. Bump the AppConfig.schema_version default value
      2. Write an upgrade function for app config in config.py
      3. Update the above data model to match the new schema
    '''
    assert AppConfig.schema['properties'] == AppConfig_v3.schema['properties'], \
            'Current AppConfig schema does not match schema_version = 3'

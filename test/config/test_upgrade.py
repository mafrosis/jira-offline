'''
Tests for the config.upgrade module
'''
from dataclasses import dataclass
import datetime
import os
from typing import Dict, List, Optional, Set
from unittest import mock

from jira_offline.config import upgrade_schema
from jira_offline.config.user_config import write_default_user_config
from jira_offline.models import AppConfig
from jira_offline.utils.serializer import DataclassSerializer


@mock.patch('jira_offline.config.upgrade.config_upgrade_1_to_2')
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
class CustomFields(DataclassSerializer):
    epic_link: Optional[str]
    epic_name: Optional[str]
    sprint: Optional[str]
    story_points: Optional[str]
    parent_link: Optional[str]
    extended: Optional[Dict[str, str]]

@dataclass
class IssueType(DataclassSerializer):
    name: str
    statuses: Set[str]

@dataclass
class OAuth(DataclassSerializer):
    access_token: Optional[str]
    access_token_secret: Optional[str]
    consumer_key: Optional[str]
    key_cert: Optional[str]

@dataclass  # pylint: disable=too-many-instance-attributes
class ProjectMeta(DataclassSerializer):  # pylint: disable=too-many-instance-attributes
    key: str
    name: Optional[str]
    username: Optional[str]
    password: Optional[str]
    protocol: Optional[str]
    hostname: Optional[str]
    last_updated: Optional[str]
    issuetypes: Dict[str, IssueType]
    customfields: Optional[CustomFields]
    priorities: Optional[Set[str]]
    components: Optional[Set[str]]
    oauth: Optional[OAuth]
    ca_cert: Optional[str]
    timezone: datetime.tzinfo
    jira_id: Optional[str]
    config: Optional['AppConfig']
    default_reporter: Optional[str]

@dataclass
class UserConfig(DataclassSerializer):
    @dataclass
    class Sync:
        page_size: int
    sync: Sync

    @dataclass
    class Display:
        ls_fields: List[str]
        ls_fields_verbose: List[str]
        ls_default_filter: str
    display: Display

    @dataclass
    class Issue:
        default_reporter: Dict[str, str]
    issue: Issue

    customfields: Dict[str, dict]

@dataclass
class AppConfig_v3(DataclassSerializer):
    schema_version: int
    projects: Dict[str, ProjectMeta]
    user_config_filepath: str
    user_config_hash: str
    user_config: UserConfig

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

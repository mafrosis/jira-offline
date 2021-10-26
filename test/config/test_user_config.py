'''
Tests for the config.user_config module
'''
from unittest import mock

import pytest

from jira_offline.config.user_config import _apply_user_config, load_user_config
from jira_offline.models import AppConfig, ProjectMeta


@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_config__calls_load_user_config(mock_os, mock_apply_user_config):
    '''
    Test load_user_config calls _apply_user_config
    '''
    # config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = '''
    [display]
    ls = status,summary
    '''

    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        load_user_config(AppConfig())

    assert mock_apply_user_config.called


@mock.patch('jira_offline.config.user_config.apply_user_config_to_project')
@mock.patch('jira_offline.config.user_config.hashlib')
@mock.patch('jira_offline.config.user_config.os')
@mock.patch('builtins.open')
def test_apply_user_config__does_not_apply_when_config_hash_unchanged(
        mock_open, mock_os, mock_hashlib, mock_apply_user_config_to_project, project
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

    _apply_user_config(config)

    assert mock_apply_user_config_to_project.called is False


@mock.patch('jira_offline.config.user_config.apply_user_config_to_project')
@mock.patch('jira_offline.config.user_config.hashlib')
@mock.patch('jira_offline.config.user_config.os')
@mock.patch('builtins.open')
def test_apply_user_config__applies_when_config_hash_is_changed(
        mock_open, mock_os, mock_hashlib, mock_apply_user_config_to_project, project
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

    _apply_user_config(config)

    assert mock_apply_user_config_to_project.called is True


@mock.patch('jira_offline.config.user_config.apply_user_config_to_project')
@mock.patch('jira_offline.config.user_config.hashlib')
@mock.patch('jira_offline.config.user_config.os')
@mock.patch('builtins.open')
def test_apply_user_config__apply_function_is_called_once_for_each_project(
        mock_open, mock_os, mock_hashlib, mock_apply_user_config_to_project, project
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

    _apply_user_config(config)

    assert mock_apply_user_config_to_project.call_count == 2


@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_user_config__handles_comma_separated_list(mock_os, mock_apply_user_config):
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
        load_user_config(config)

    assert config.user_config.display.ls_fields == ['status', 'summary']


@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_user_config__sync_handles_integer_page_size(mock_os, mock_apply_user_config):
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
        load_user_config(config)

    assert config.user_config.sync.page_size == 99


@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_user_config__sync_ignores_non_integer_page_size(mock_os, mock_apply_user_config):
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
        load_user_config(config)

    assert config.user_config.sync.page_size == 25


@pytest.mark.parametrize('customfield_name', [
    ('story-points'),
    ('parent-link'),
])
@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_user_config__customfields_handles_firstclass_issue_attributes(
        mock_os, mock_apply_user_config, customfield_name
    ):
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
        load_user_config(config)

    assert config.user_config.customfields['*'][customfield_name.replace('-', '_')] == 'customfield_10102'


@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_user_config__customfields_ignore_reserved_keyword(mock_os, mock_apply_user_config):
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
        load_user_config(config)

    assert 'priority' not in config.user_config.customfields


@pytest.mark.parametrize('customfield_value', [
    ('customfield1'),
    ('customfield_xxx'),
    ('10101'),
    (''),
])
@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_user_config__customfields_ignore_invalid(
        mock_os, mock_apply_user_config, customfield_value
    ):
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
        load_user_config(config)

    assert 'story_points' not in config.user_config.customfields


@mock.patch('jira_offline.config.user_config._apply_user_config')
@mock.patch('jira_offline.config.user_config.os')
def test_load_user_config__per_project_section__handles_global_and_specific(mock_os, mock_apply_user_config):
    '''
    Ensure overriding user-defined customfield set per-Jira host and per-project is loaded correctly
    '''
    # Config file exists
    mock_os.path.exists.return_value = True

    user_config_fixture = '''
    [issue]
    default-reporter = dave

    [issue jira.example.com]
    default-reporter = bob

    [issue EGG]
    default-reporter = sue
    '''

    config = AppConfig()

    # Mock return from open() to return the config.ini fixture
    with mock.patch('builtins.open', mock.mock_open(read_data=user_config_fixture)):
        load_user_config(config)

    assert config.user_config.issue.default_reporter['*'] == 'dave'
    assert config.user_config.issue.default_reporter['jira.example.com'] == 'bob'
    assert config.user_config.issue.default_reporter['EGG'] == 'sue'

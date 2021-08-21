'''
Tests for the config.user_config module
'''
from unittest import mock

import pytest

from jira_offline.config.user_config import load_user_config
from jira_offline.models import AppConfig


@mock.patch('jira_offline.config.user_config.os')
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
        load_user_config(config)

    assert config.display.ls_fields == ['status', 'summary']



@mock.patch('jira_offline.config.user_config.os')
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
        load_user_config(config)

    assert config.sync.page_size == 99


@mock.patch('jira_offline.config.user_config.os')
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
        load_user_config(config)

    assert config.sync.page_size == 25


@pytest.mark.parametrize('customfield_name', [
    ('story-points'),
    ('parent-link'),
])
@mock.patch('jira_offline.config.user_config.os')
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
        load_user_config(config)

    assert config.customfields['*'][customfield_name.replace('-', '_')] == 'customfield_10102'


@mock.patch('jira_offline.config.user_config.os')
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
        load_user_config(config)

    assert 'priority' not in config.customfields


@pytest.mark.parametrize('customfield_value', [
    ('customfield1'),
    ('customfield_xxx'),
    ('10101'),
    (''),
])
@mock.patch('jira_offline.config.user_config.os')
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
        load_user_config(config)

    assert 'story_points' not in config.customfields


@mock.patch('jira_offline.config.user_config.os')
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
        load_user_config(config)

    assert 'arbitrary' not in config.customfields
    assert config.customfields['*']['arbitrary'] == 'customfield_10144'
    assert config.customfields['jira.example.com']['arbitrary'] == 'customfield_10155'
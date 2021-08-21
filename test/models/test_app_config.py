'''
Tests for the AppConfig class
'''
import dataclasses

from jira_offline.models import AppConfig, CustomFields


def test_app_config_model__iter_customfield_names_includes_core():
    '''
    Validate core customfields are in the return from AppConfig.iter_customfields()
    '''
    # Determine the current set of core customfields from the Customfields class
    core_customfields = {f.name for f in dataclasses.fields(CustomFields) if f.name != 'extended'}

    config = AppConfig()
    assert config.iter_customfield_names() == core_customfields


def test_app_config_model__iter_customfield_names_includes_user_defined():
    '''
    Validate user-defined customfields are in the return from AppConfig.iter_customfields()
    '''
    config = AppConfig()

    config.customfields = {
        '*': {
            'arbitrary-1': 'customfield_10400'
        },
        'jira.example.com': {
            'arbitrary-2': 'customfield_10400'
        },
    }

    assert 'arbitrary-1' in config.iter_customfield_names()
    assert 'arbitrary-2' in config.iter_customfield_names()

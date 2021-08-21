'''
Tests for the AppConfig class
'''
import dataclasses

from jira_offline.models import AppConfig, CustomFields


def test_app_config_model__iter_customfields_includes_core():
    '''
    Validate core customfields are in the return from AppConfig.iter_customfields()
    '''
    # Determine the current set of core customfields from the Customfields class
    core_customfields = {f.name for f in dataclasses.fields(CustomFields) if f.name != 'extended'}

    config = AppConfig()
    assert config.iter_customfields() == core_customfields

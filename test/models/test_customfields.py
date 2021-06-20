'''
Tests for the CustomFields model
'''
import dataclasses

from jira_offline.models import CustomFields, Issue


def test_customfields_model__issue_model_has_matching_attributes():
    '''
    Ensure that all attributes on the CustomFields model are also defined on the Issue model
    '''
    issue_attribute_names = [f.name for f in dataclasses.fields(Issue)]

    for customfield_attribute in dataclasses.fields(CustomFields):
        assert customfield_attribute.name in issue_attribute_names

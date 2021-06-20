'''
Tests for the issue_to_jiraapi_update function in utils.convert module
'''
import copy
import decimal

import pytest

from fixtures import ISSUE_1, JIRAAPI_OBJECT
from jira_offline.models import CustomFields, Issue, ProjectMeta
from jira_offline.utils.convert import issue_to_jiraapi_update, jiraapi_object_to_issue


def test_jiraapi_object_to_issue__handles_customfields(mock_jira):
    '''
    Ensure jiraapi_object_to_issue extracts customfield value into correct Issue attribute
    '''
    customfields = CustomFields(
        epic_ref='customfield_10100',
        epic_name='customfield_10200',
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    issue = jiraapi_object_to_issue(project, JIRAAPI_OBJECT)
    assert issue.epic_ref == 'TEST-1'


def test_jiraapi_object_to_issue__handles_customfields_2(mock_jira):
    '''
    Ensure jiraapi_object_to_issue extracts customfield value into correct Issue attribute
    '''
    customfields = CustomFields(
        epic_ref='customfield_10100',
        epic_name='customfield_10200',
        story_points='customfield_10400',
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    jiraobj = copy.copy(JIRAAPI_OBJECT)
    jiraobj['fields']['customfield_10400'] = '1.234'

    issue = jiraapi_object_to_issue(project, JIRAAPI_OBJECT)
    assert issue.epic_ref == 'TEST-1'
    assert issue.story_points == decimal.Decimal('1.234')


@pytest.mark.parametrize('modified', [
    {'assignee'},
    {'fix_versions', 'summary'},
])
def test_issue_to_jiraapi_update__returns_only_fields_passed_in_modified(mock_jira, project, modified):
    '''
    Ensure issue_to_jiraapi_update returns only set of fields passed in modified parameter
    '''
    issue_dict = issue_to_jiraapi_update(project, Issue.deserialize(ISSUE_1), modified)
    assert issue_dict.keys() == modified


@pytest.mark.parametrize('modified', [
    {'assignee'},
    {'issuetype'},
    {'reporter'},
])
def test_issue_to_jiraapi_update__fields_are_formatted_correctly(mock_jira, project, modified):
    '''
    Ensure issue_to_jiraapi_update formats some fields correctly
    '''
    issue_dict = issue_to_jiraapi_update(project, Issue.deserialize(ISSUE_1), modified)
    assert 'name' in issue_dict[next(iter(modified))]


def test_issue_to_jiraapi_update__handles_class_property(mock_jira, project):
    '''
    Ensure issue_to_jiraapi_update handles @property fields on Issue class
    '''
    issue_dict = issue_to_jiraapi_update(project, Issue.deserialize(ISSUE_1), {'priority'})
    assert issue_dict.keys() == {'priority'}


def test_issue_to_jiraapi_update__all_fields_are_returned_for_new_issue(mock_jira, project):
    '''
    Ensure issue_to_jiraapi_update returns all mandatory and new fields for a new Issue
    '''
    issue_dict = issue_to_jiraapi_update(
        project,
        Issue.deserialize(ISSUE_1),
        {'issuetype', 'summary', 'epic_ref', 'description', 'fix_versions', 'reporter'}
    )

    assert issue_dict == {
        project.customfields.epic_ref: 'TEST-1',
        'description': 'This is a story or issue',
        'fix_versions': ['0.1'],
        'issuetype': {'name': 'Story'},
        'reporter': {'name': 'danil1'},
        'summary': 'This is the story summary',
    }

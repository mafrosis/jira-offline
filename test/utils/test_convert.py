'''
Tests for the issue_to_jiraapi_update function in utils.convert module
'''
import decimal
from unittest import mock

import pytest

from fixtures import ISSUE_1, ISSUE_NEW, JIRAAPI_OBJECT
from jira_offline.models import CustomFields, Issue, ProjectMeta
from jira_offline.utils.convert import issue_to_jiraapi_update, jiraapi_object_to_issue, preprocess_sprint


def test_jiraapi_object_to_issue__handles_customfields(mock_jira):
    '''
    Ensure jiraapi_object_to_issue extracts customfield value into correct Issue attribute
    '''
    customfields = CustomFields(
        epic_link='customfield_10100',
        epic_name='customfield_10200',
        sprint='customfield_10300',
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    issue = jiraapi_object_to_issue(project, JIRAAPI_OBJECT)
    assert issue.epic_link == 'TEST-1'


def test_jiraapi_object_to_issue__handles_customfields_2(mock_jira):
    '''
    Ensure jiraapi_object_to_issue extracts customfield value into correct Issue attribute
    '''
    customfields = CustomFields(
        epic_link='customfield_10100',
        epic_name='customfield_10200',
        sprint='customfield_10300',
        story_points='customfield_10400',
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    with mock.patch.dict(JIRAAPI_OBJECT['fields'], {'customfield_10400': '1.234'}):
        issue = jiraapi_object_to_issue(project, JIRAAPI_OBJECT)

    assert issue.epic_link == 'TEST-1'
    assert issue.story_points == decimal.Decimal('1.234')


def test_jiraapi_object_to_issue__handles_customfields_extended(mock_jira):
    '''
    Ensure jiraapi_object_to_issue extracts extended customfield value into correct Issue attribute
    '''
    customfields = CustomFields(
        epic_link='customfield_10100',
        epic_name='customfield_10200',
        sprint='customfield_10300',
        extended={
            'arbitrary_key': 'customfield_10111',
        }
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    with mock.patch.dict(JIRAAPI_OBJECT['fields'], {'customfield_10111': 'arbitrary_value'}):
        issue = jiraapi_object_to_issue(project, JIRAAPI_OBJECT)

    assert issue.epic_link == 'TEST-1'
    assert issue.extended['arbitrary_key'] == 'arbitrary_value'


def test_issue_to_jiraapi_update__handles_customfields(mock_jira):
    '''
    Ensure issue_to_jiraapi_update converts Issue customfield attributes into the Jira API update format
    '''
    customfields = CustomFields(
        epic_link='customfield_10100',
        epic_name='customfield_10200',
        sprint='customfield_10300',
        story_points='customfield_10400',
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    issue_fixture = Issue.deserialize(ISSUE_1)
    issue_fixture.story_points = decimal.Decimal('1.234')

    update_dict = issue_to_jiraapi_update(project, issue_fixture, {'story_points'})
    assert 'customfield_10400' in update_dict
    assert update_dict['customfield_10400'] == '1.234'


def test_issue_to_jiraapi_update__handles_customfields_extended(mock_jira):
    '''
    Ensure issue_to_jiraapi_update converts Issue customfield extended attributes into the Jira API update format
    '''
    customfields = CustomFields(
        epic_link='customfield_10100',
        epic_name='customfield_10200',
        sprint='customfield_10300',
        extended={
            'arbitrary_key': 'customfield_10111',
        }
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    issue_fixture = Issue.deserialize(ISSUE_1)
    issue_fixture.extended['arbitrary_key'] = 'arbitrary_value'

    update_dict = issue_to_jiraapi_update(project, issue_fixture, {'extended.arbitrary_key'})
    assert 'customfield_10111' in update_dict
    assert update_dict['customfield_10111'] == 'arbitrary_value'


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
    {'priority'},
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


def test_issue_to_jiraapi_update__core_mandatory_fields_returned_for_new_issue(mock_jira):
    '''
    Ensure issue_to_jiraapi_update returns all mandatory and new fields for a new Issue
    '''
    # Setup the project configuration with customfields
    customfields = CustomFields(
        epic_link='customfield_10100',
        epic_name='customfield_10200',
        sprint='customfield_10300',
    )
    project = ProjectMeta(key='TEST', jira_id='10000', customfields=customfields)

    # Create a plain & simple new issue with no extra pre-set fields
    with mock.patch.dict(ISSUE_NEW, {'fix_versions': set(), 'epic_link': None, 'reporter': None}):
        new_issue = Issue.deserialize(ISSUE_NEW)

    issue_dict = issue_to_jiraapi_update(
        project, new_issue, {'project_id', 'issuetype', 'summary', 'key'}
    )

    assert issue_dict == {
        'project': {'id': '10000'},
        'issuetype': {'name': 'Story'},
        'summary': 'This is the story summary',
    }


def test_issue_to_jiraapi_update__customfields_and_extended_customfields_returned_for_new_issue(mock_jira):
    '''
    Ensure issue_to_jiraapi_update returns customfields and extended customfields for a new Issue
    '''
    # Setup the project configuration with customfields
    customfields = CustomFields(
        epic_link='customfield_10100',
        epic_name='customfield_10200',
        sprint='customfield_10300',
        extended={
            'arbitrary_key': 'customfield_10111',
        }
    )
    project = ProjectMeta(key='TEST', jira_id='10000', customfields=customfields)

    # Create a new issue with a customfield, and an extended customfield
    with mock.patch.dict(ISSUE_NEW, {
            'fix_versions': set(),
            'epic_link': 'EPIC-1',
            'reporter': None,
            'extended': {'arbitrary_key': 'arbitrary_value'}
        }):
        new_issue = Issue.deserialize(ISSUE_NEW)

    issue_dict = issue_to_jiraapi_update(
        project, new_issue, {'project_id', 'issuetype', 'summary', 'key', 'description', 'epic_link', 'extended.arbitrary_key'}
    )

    assert issue_dict == {
        'project': {'id': '10000'},
        'description': 'This is a story or issue',
        'issuetype': {'name': 'Story'},
        'summary': 'This is the story summary',

        'customfield_10100': 'EPIC-1',
        'customfield_10111': 'arbitrary_value',
    }


@pytest.mark.parametrize('sprint', [
    [{'id': 123, 'name': 'SCRUM Sprint 2', 'state': 'active', 'boardId': 99, 'goal': 'Fix Things', 'startDate': '2020-01-01T00:00:00.000Z', 'endDate': '2020-01-14T00:00:00.000Z'}],
    ['com.atlassian.greenhopper.service.sprint.Sprint@64cd2ea7[id=2,rapidViewId=3,state=FUTURE,name=SCRUM Sprint 2,startDate=<null>,endDate=<null>,completeDate=<null>,activatedDate=<null>,sequence=2,goal=<null>]'],
])
def test_preprocess_sprint__returns_sprint_name(sprint):
    '''
    Ensure the API conversion util function `preprocess_sprint` parses the sprint name from the API
    returns from different Jiras.
    '''
    assert preprocess_sprint(sprint) == 'SCRUM Sprint 2'

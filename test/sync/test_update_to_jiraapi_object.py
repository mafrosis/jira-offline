'''
Tests for the issue_to_jiraapi_update function in sync module
'''
import pytest

from fixtures import ISSUE_1
from jira_cli.models import Issue
from jira_cli.sync import issue_to_jiraapi_update


@pytest.mark.parametrize('modified', [
    {'assignee'},
    {'fixVersions', 'summary'},
])
def test_issue_to_jiraapi_update__returns_only_fields_passed_in_modified(modified):
    '''
    Ensure issue_to_jiraapi_update returns only set of fields passed in modified parameter
    '''
    issue_dict = issue_to_jiraapi_update(Issue.deserialize(ISSUE_1), modified)
    assert issue_dict.keys() == modified


@pytest.mark.parametrize('modified', [
    {'assignee'},
    {'issuetype'},
    {'reporter'},
])
def test_issue_to_jiraapi_update__fields_are_formatted_correctly(modified):
    '''
    Ensure issue_to_jiraapi_update formats some fields correctly
    '''
    issue_dict = issue_to_jiraapi_update(Issue.deserialize(ISSUE_1), modified)
    assert 'name' in issue_dict[modified.pop()]

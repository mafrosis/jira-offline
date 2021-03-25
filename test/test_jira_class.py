'''
Tests for the Jira API class in main.py

Unlike other tests, these access the class directly, not via the mock_jira interface defined in
conftest.py
'''
from unittest import mock

import pytest

from fixtures import EPIC_1, ISSUE_1, ISSUE_2, ISSUE_MISSING_EPIC, ISSUE_NEW
from jira_offline.exceptions import (EpicNotFound, EstimateFieldUnavailable, FailedAuthError,
                                     JiraApiError, JiraNotConfigured, ProjectDoesntExist)
from jira_offline.models import CustomFields, Issue, IssueType, ProjectMeta


@mock.patch('jira_offline.jira.jsonlines')
@mock.patch('jira_offline.jira.os')
@mock.patch('builtins.open')
def test_jira__load_issues__calls_deserialize_for_each_line_in_cache(mock_open, mock_os, mock_jsonlines, mock_jira_core):
    '''
    Ensure load_issues calls Issue.deserialize for each line in the cache file
    '''
    # issues cache is present, and non-zero in size
    mock_os.path.exists.return_value = True
    mock_os.stat.return_value.st_size = 1

    # mock contents of issue cache, as read from disk
    mock_jsonlines.Reader.return_value.iter.return_value = [EPIC_1, ISSUE_1, ISSUE_MISSING_EPIC]

    with mock.patch('jira_offline.jira.Issue.deserialize') as mock_issue_deserialize:
        mock_jira_core.load_issues()
        assert mock_issue_deserialize.call_count == 3


@mock.patch('jira_offline.jira.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__calls_write_all(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues calls jsonlines.write_all. If this test is failing it indicates a bug in the
    write_issues() method.
    '''
    mock_jira_core['TEST-1'] = Issue.deserialize(EPIC_1)

    mock_jira_core.write_issues()

    assert mock_jsonlines.Writer.return_value.write_all.called


@mock.patch('jira_offline.jira.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__calls_serialize_for_each_item_in_self(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues calls Issue.serialize for each line in self (which implements dict)
    '''
    mock_jira_core['TEST-1'] = Issue.deserialize(EPIC_1)
    mock_jira_core['TEST-71'] = Issue.deserialize(ISSUE_1)
    mock_jira_core['TEST-73'] = Issue.deserialize(ISSUE_MISSING_EPIC)

    with mock.patch('jira_offline.jira.Issue.serialize') as mock_issue_serialize:
        mock_jira_core.write_issues()
        assert mock_issue_serialize.call_count == 3


@mock.patch('jira_offline.jira.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__does_call_issue_diff_for_existing_and_modified_issues(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues DOES call Issue.diff on modified issues which already exist on Jira
    '''
    issue = mock_jira_core['TEST-72'] = Issue.deserialize(ISSUE_2)

    # patch the Issue's diff method, then set modified=False as the patch changes the modified flag!
    with mock.patch.object(issue, 'diff', mock.MagicMock()):
        issue.modified = False
        issue.summary = 'Test'

        mock_jira_core.write_issues()

        assert issue.diff.called is True


@mock.patch('jira_offline.jira.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__doesnt_call_issue_diff_for_non_modified_issues(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues DOESN'T call Issue.diff for issues which already exist on Jira
    '''
    issue = mock_jira_core['TEST-71'] = Issue.deserialize(ISSUE_1)

    # patch the Issue's diff method, then set modified=False as the patch changes the modified flag!
    with mock.patch.object(issue, 'diff', mock.MagicMock()):
        issue.modified = False

        mock_jira_core.write_issues()

        assert issue.diff.called is False


@mock.patch('jira_offline.jira.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__doesnt_call_issue_diff_for_non_existing_issues(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues DOESN'T call Issue.diff for issues which already exist on Jira
    '''
    issue = mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

    # patch the Issue's diff method, then set modified=False as the patch changes the modified flag!
    with mock.patch.object(issue, 'diff', mock.MagicMock()):
        issue.modified = False

        mock_jira_core.write_issues()

        assert issue.diff.called is False


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__extracts_priorities(mock_api_get, mock_jira_core, project):
    '''
    Ensure get_project_meta() method extracts project priorities from a project
    '''
    # mock out call to _get_project_issue_statuses and _get_project_components
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()

    # mock return from Jira createmeta API call
    mock_api_get.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'id': '5',
                'name': 'Story',
                'fields': {
                    'priority': {
                        'name': 'priority',
                        'allowedValues': [{'name': 'Egg'}, {'name': 'Bacon'}],
                    },
                },
            }]
        }]
    }

    mock_jira_core.get_project_meta(project)

    assert mock_api_get.called
    assert project.priorities == {'Bacon', 'Egg'}


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__extracts_issuetypes(mock_api_get, mock_jira_core, project):
    '''
    Ensure get_project_meta() method parses the issuetypes for a project
    '''
    # mock out call to _get_project_issue_statuses and _get_project_components
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()

    # mock return from Jira createmeta API call
    mock_api_get.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'id': '5',
                'name': 'Story',
                'fields': {
                    'summary': {'name': 'Summary'},
                },
            },{
                'id': '18500',
                'name': 'Custom_IssueType',
                'fields': {
                    'summary': {
                        'name': 'Summary'
                    },
                    'customfield_10104': {
                        'schema': {
                            'customId': 10104
                        },
                        'name': 'Story Points',
                    },
                },
            }]
        }]
    }

    mock_jira_core.get_project_meta(project)

    assert mock_api_get.called
    assert project.issuetypes == {
        'Story': IssueType(name='Story'),
        'Custom_IssueType': IssueType(name='Custom_IssueType')
    }


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__handles_removal_of_issuetype(mock_api_get, mock_jira_core, project):
    '''
    Ensure get_project_meta() method handles when an issuetype is removed from a project on Jira

    The project fixture includes the Story issuetype, this should be removed if not in the API result
    '''
    # mock out call to _get_project_issue_statuses and _get_project_components
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()

    # mock return from Jira createmeta API call
    mock_api_get.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'id': '5',
                'name': 'Epic',
                'fields': {
                    'summary': {'name': 'Summary'},
                },
            }]
        }]
    }

    mock_jira_core.get_project_meta(project)

    assert mock_api_get.called
    assert project.issuetypes == {
        'Epic': IssueType(name='Epic')
    }


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__extracts_custom_fields(mock_api_get, mock_jira_core, project):
    '''
    Ensure get_project_meta() method parses the custom_fields for a project
    '''
    # mock out call to _get_project_issue_statuses and _get_project_components
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()

    # mock return from Jira createmeta API call
    mock_api_get.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'self': 'https://example.com/rest/api/2/issuetype/5',
                'id': '5',
                'name': 'Epic',
                'fields': {
                    'summary': {
                        'name': 'Summary'
                    },
                    'customfield_10104': {
                        'schema': {
                            'customId': 10104
                        },
                        'name': 'Epic Name',
                    },
                    'customfield_10106': {
                        'schema': {
                            'customId': 10106
                        },
                        'name': 'Story Points',
                    },
                },
            }]
        }]
    }

    mock_jira_core.get_project_meta(project)

    assert mock_api_get.called
    assert project.custom_fields == CustomFields(epic_name='10104', estimate='10106')


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__handles_no_priority_for_issuetype(mock_api_get, mock_jira_core, project):
    '''
    Ensure get_project_meta() method doesn't choke if an issuetype has no priority field
    '''
    # mock out call to _get_project_issue_statuses and _get_project_components
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()

    # mock return from Jira createmeta API call
    mock_api_get.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'self': 'https://example.com/rest/api/2/issuetype/5',
                'id': '5',
                'name': 'Epic',
                'fields': {
                    'customfield_10106': {
                        'schema': {
                            'customId': 10106
                        },
                        'name': 'Story Points',
                    },
                },
            }]
        }]
    }

    mock_jira_core.get_project_meta(project)

    assert mock_api_get.called
    assert project.custom_fields == CustomFields(estimate='10106')


@mock.patch('jira_offline.utils.decorators.get_user_creds')
@mock.patch('jira_offline.utils.api._request', side_effect=FailedAuthError)
def test_jira__get_project_meta__auth_retry_decorator(mock_api_request, mock_get_user_creds, mock_jira_core, project):
    '''
    Ensure a password prompt is shown when we have an API authentication failure
    '''
    # mock out call to _get_project_issue_statuses and _get_project_components
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()

    # swallow the second FailedAuthError, the first one _should_ trigger a call to `get_user_creds`
    with pytest.raises(FailedAuthError):
        mock_jira_core.get_project_meta(project)

    assert mock_get_user_creds.called is True


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__raises_project_doesnt_exist(mock_api_get, mock_jira_core):
    '''
    Ensure ProjectDoesntExist exception is raised if nothing returned by API createmeta call
    '''
    # mock return from Jira createmeta API call
    mock_api_get.return_value = {'projects': []}

    with pytest.raises(ProjectDoesntExist):
        mock_jira_core.get_project_meta(ProjectMeta(key='TEST'))


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_issue_statuses__extracts_statuses_for_issuetypes(mock_api_get, mock_jira_core, project):
    '''
    Ensure _get_project_issue_statuses() method doesn't choke if an issuetype has no priority field
    '''
    # mock return from Jira statuses API call
    mock_api_get.return_value = [{
        'id': '10005',
        'name': 'Story',
        'statuses': [{'name': 'Egg'}, {'name': 'Bacon'}]
    }]

    mock_jira_core._get_project_issue_statuses(project)

    assert mock_api_get.called
    assert project.issuetypes['Story'].statuses == {'Egg', 'Bacon'}


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_components__does_not_fail(mock_api_get, mock_jira_core, project):
    '''
    Ensure _get_project_components() method has no dumb errors
    '''
    # mock return from Jira components API call
    mock_api_get.return_value = [{
        'id': '10005',
        'name': 'Egg',
    },{
        'id': '10006',
        'name': 'Bacon',
    }]

    mock_jira_core._get_project_components(project)

    assert mock_api_get.called
    assert project.components == {'Egg', 'Bacon'}


@mock.patch('jira_offline.jira.jiraapi_object_to_issue', return_value=Issue.deserialize(ISSUE_1))
@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__removes_fields_which_cannot_be_posted_for_new_issue(
        mock_api_post, mock_jiraapi_object_to_issue, mock_jira_core, project
    ):
    '''
    Some fields cannot be posted to the Jira API. Ensure they are removed before the API call.
    '''
    # dont write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # add new issue to the jira object
    mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

    # mock the fetch_issue() call that happens after successful new_issue() call
    mock_jira_core.fetch_issue = mock.Mock()

    mock_jira_core.new_issue(
        project,
        fields={
            'project_id': 'notarealprojecthash',
            'key': ISSUE_NEW['key'],
            'summary': 'A summary',
            'issuetype': {'name': 'Story'},
        }
    )

    # assert "key" and "status" are removed
    mock_api_post.assert_called_with(project, 'issue', data={'fields': {'summary': 'A summary', 'issuetype': {'name': 'Story'}}})


@pytest.mark.parametrize('error_msg,exception', [
    ('gh.epic.error.not.found', EpicNotFound),
    ("Field 'estimate' cannot be set", EstimateFieldUnavailable),
    ('cannot be set. It is not on the appropriate screen, or unknown.', JiraNotConfigured),
])
@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__raises_specific_exceptions(mock_api_post, mock_jira_core, project, error_msg, exception):
    '''
    Ensure correct custom exception is raised when specific string found in Jira API error message
    '''
    # mock the Jira library to raise
    mock_api_post.side_effect = JiraApiError(error_msg)

    with pytest.raises(exception):
        mock_jira_core.new_issue(
            project,
            fields={
                'project_id': 'notarealprojecthash',
                'key': ISSUE_NEW['key'],
                'status': 'Backlog',
                'summary': 'A summary',
                'issuetype': {'name': 'Story'},
            }
        )


@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__removes_temp_key_when_new_post_successful(
        mock_api_post, mock_jira_core, project
    ):
    '''
    Ensure a successful post of a new Issue deletes the old temp UUID key from self
    '''
    # dont write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # add new issue to the jira object, under temporary key
    mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

    # mock the fetch_issue() call that happens after successful new_issue() call
    mock_jira_core.fetch_issue = mock.Mock(return_value=Issue.deserialize(ISSUE_1))

    mock_jira_core.new_issue(
        project,
        fields={
            'project_id': 'notarealprojecthash',
            'key': ISSUE_NEW['key'],
            'status': 'Backlog',
            'summary': 'A summary',
            'issuetype': {'name': 'Story'},
        }
    )

    # assert temporary key has been removed
    assert ISSUE_NEW['key'] not in mock_jira_core
    # assert new key returned from Jira API has been added (found in return from jiraapi_object_to_issue)
    assert ISSUE_1['key'] in mock_jira_core


@mock.patch('jira_offline.jira.jiraapi_object_to_issue')
@mock.patch('jira_offline.jira.api_get')
def test_fetch_issue__returns_output_from_jiraapi_object_to_issue(
        mock_api_get, mock_jiraapi_object_to_issue, mock_jira_core, project
    ):
    '''
    Ensure jira.fetch_issue() returns the output directly from jiraapi_object_to_issue()
    '''
    mock_jiraapi_object_to_issue.return_value = 1

    ret = mock_jira_core.fetch_issue(project, ISSUE_1['key'])
    assert ret == 1

    mock_api_get.assert_called_with(project, 'issue/{}'.format(ISSUE_1['key']))
    assert mock_jiraapi_object_to_issue.called


def test_keys__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.keys() respects a configured jira.filter parameter
    '''
    mock_jira_core['TEST-71'] = Issue.deserialize(ISSUE_1, project=ProjectMeta('FIRST'))
    mock_jira_core['TEST-72'] = Issue.deserialize(ISSUE_2, project=ProjectMeta('SECOND'))

    assert list(mock_jira_core.keys()) == ['TEST-71', 'TEST-72']

    mock_jira_core.filter.project_key = 'SECOND'

    assert list(mock_jira_core.keys()) == ['TEST-72']


def test_values__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.values() respects a configured jira.filter parameter
    '''
    mock_jira_core['TEST-71'] = Issue.deserialize(ISSUE_1, project=ProjectMeta('FIRST'))
    mock_jira_core['TEST-72'] = Issue.deserialize(ISSUE_2, project=ProjectMeta('SECOND'))

    assert list(mock_jira_core.values()) == [mock_jira_core['TEST-71'], mock_jira_core['TEST-72']]

    mock_jira_core.filter.project_key = 'SECOND'

    assert list(mock_jira_core.values()) == [mock_jira_core['TEST-72']]


def test_items__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.items() respects a configured jira.filter parameter
    '''
    mock_jira_core['TEST-71'] = Issue.deserialize(ISSUE_1, project=ProjectMeta('FIRST'))
    mock_jira_core['TEST-72'] = Issue.deserialize(ISSUE_2, project=ProjectMeta('SECOND'))

    assert list(mock_jira_core.items()) == [
        ('TEST-71', mock_jira_core['TEST-71']),
        ('TEST-72', mock_jira_core['TEST-72']),
    ]

    mock_jira_core.filter.project_key = 'SECOND'

    assert list(mock_jira_core.items()) == [
        ('TEST-72', mock_jira_core['TEST-72']),
    ]

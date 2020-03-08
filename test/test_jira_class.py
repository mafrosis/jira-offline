'''
Tests for the Jira API class in main.py

Unlike other tests, these access the class directly, not via the mock_jira interface defined in
conftest.py
'''
from unittest import mock

import jira as mod_jira
import pytest

from fixtures import EPIC_1, ISSUE_1, ISSUE_MISSING_EPIC, ISSUE_NEW
from jira_cli.exceptions import (EpicNotFound, EstimateFieldUnavailable, JiraNotConfigured,
                                 ProjectDoesntExist)
from jira_cli.main import Jira
from jira_cli.models import AppConfig, CustomFields, Issue, OAuth, ProjectMeta


@mock.patch('jira_cli.main.load_config')
@mock.patch('jira_cli.main.mod_jira')
def test_jira__connect__returns_connection_from_cache(mock_mod_jira, mock_load_config, project):
    '''
    Ensure connect() returns and existing connection if cached
    '''
    jira = Jira()
    jira.config = AppConfig(projects={project.id: project})
    jira._connections = {project.id: mock_mod_jira.JIRA}

    # pass a ProjectMeta object into connect
    jira.connect(project)

    # assert that a new connection is not created
    assert not mock_mod_jira.JIRA.called


@mock.patch('jira_cli.main.load_config')
@mock.patch('jira_cli.main.mod_jira')
def test_jira__connect__creates_a_new_connection(mock_mod_jira, mock_load_config, project):
    '''
    Ensure connect() returns and existing connection if cached
    '''
    jira = Jira()
    jira.config = AppConfig()

    # pass a ProjectMeta object into connect
    jira.connect(project)

    # assert that a new connection is not created
    assert mock_mod_jira.JIRA.called


@mock.patch('jira_cli.main.load_config')
@mock.patch('jira_cli.main.mod_jira')
def test_jira__connect__passes_basic_auth_to_mod_jira(mock_mod_jira, mock_load_config, project):
    '''
    Ensure connect() passes username/password to mod_jira.JIRA constructor when username supplied
    '''
    jira = Jira()
    jira.config = AppConfig()

    project.username = 'tester'
    project.password = 'faked'
    project.oauth = None

    # pass a ProjectMeta object into connect
    jira.connect(project)

    # validate the parameter passed into the JIRA constructor
    assert mock_mod_jira.JIRA.call_args_list[0][1]['basic_auth'] == ('tester', 'faked')


@mock.patch('jira_cli.main.load_config')
@mock.patch('jira_cli.main.mod_jira')
def test_jira__connect__passes_oauth_to_mod_jira(mock_mod_jira, mock_load_config, project):
    '''
    Ensure connect() passes oauth to mod_jira.JIRA constructor when username supplied
    '''
    jira = Jira()
    jira.config = AppConfig()

    project.username = project.password = None
    project.oauth = OAuth(
        access_token='token',
        access_token_secret='secret',
        consumer_key='ckey',
        key_cert='cert',
    )

    # pass a ProjectMeta object into connect
    jira.connect(project)

    # validate the parameter passed into the JIRA constructor
    assert mock_mod_jira.JIRA.call_args_list[0][1]['oauth'] == {
        'access_token': 'token',
        'access_token_secret': 'secret',
        'consumer_key': 'ckey',
        'key_cert': 'cert',
    }


@mock.patch('jira_cli.main.jsonlines')
@mock.patch('jira_cli.main.os')
@mock.patch('builtins.open')
def test_jira__load_issues__calls_deserialize_for_each_line_in_cache(mock_open, mock_os, mock_jsonlines, mock_jira_core):
    '''
    Ensure load_issues calls Issue.deserialize for each line in the cache file
    '''
    # issues cache is present
    mock_os.path.exists.return_value = True

    # mock contents of issue cache, as read from disk
    mock_jsonlines.Reader.return_value.iter.return_value = [EPIC_1, ISSUE_1, ISSUE_MISSING_EPIC]

    with mock.patch('jira_cli.main.Issue.deserialize') as mock_issue_deserialize:
        mock_jira_core.load_issues()
        assert mock_issue_deserialize.call_count == 3


@mock.patch('jira_cli.main.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__calls_write_all(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues calls jsonlines.write_all. If this test is failing it indicates a bug in the
    write_issues() method.
    '''
    mock_jira_core['epic1'] = Issue.deserialize(EPIC_1)

    mock_jira_core.write_issues()

    assert mock_jsonlines.Writer.return_value.write_all.called


@mock.patch('jira_cli.main.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__calls_serialize_for_each_item_in_self(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues calls Issue.serialize for each line in self (which implements dict)
    '''
    mock_jira_core['epic1'] = Issue.deserialize(EPIC_1)
    mock_jira_core['issue1'] = Issue.deserialize(ISSUE_1)
    mock_jira_core['issue2'] = Issue.deserialize(ISSUE_MISSING_EPIC)

    with mock.patch('jira_cli.main.Issue.serialize') as mock_issue_serialize:
        mock_jira_core.write_issues()
        assert mock_issue_serialize.call_count == 3


@mock.patch('jira_cli.main.jsonlines')
@mock.patch('builtins.open')
def test_jira__write_issues__calls_issue_diff_for_existing_issues_only(mock_open, mock_jsonlines, mock_jira_core):
    '''
    Ensure write_issues calls Issue.serialize for each line in self (which implements dict)
    '''
    mock_jira_core['issue1'] = Issue.deserialize(ISSUE_1)
    mock_jira_core['issue_new'] = Issue.deserialize(ISSUE_NEW)

    with mock.patch('jira_cli.main.Issue.diff'):
        mock_jira_core.write_issues()

        assert mock_jira_core['issue1'].diff.called
        assert mock_jira_core['issue_new'].diff.called


def test_jira__get_project_meta__extracts_issuetypes(mock_jira_core):
    '''
    Ensure get_project_meta() method parses the issuetypes for a project
    '''
    # mock return from Jira createmeta API call
    mock_jira_core._jira.createmeta.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'id': '5',
                'name': 'Epic',
                'fields': {},
            },{
                'id': '18500',
                'name': 'Party',
                'fields': {},
            }]
        }]
    }

    project_meta = ProjectMeta(key='BACON')

    mock_jira_core.get_project_meta(project_meta)

    assert mock_jira_core.connect.called
    assert mock_jira_core._jira.createmeta.called
    assert project_meta.name == 'Project EGG'
    assert project_meta.issuetypes == {'Epic', 'Party'}


def test_jira__get_project_meta__extracts_custom_fields(mock_jira_core):
    '''
    Ensure get_project_meta() method parses the custom_fields for a project
    '''
    # mock return from Jira createmeta API call
    mock_jira_core._jira.createmeta.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'self': 'https://example.com/rest/api/2/issuetype/5',
                'id': '5',
                'name': 'Epic',
                'fields': {
                    'customfield_10104': {
                        'required': True,
                        'schema': {
                            'type': 'string',
                            'customId': 10104
                        },
                        'name': 'Epic Name',
                        'operations': ['set']
                    },
                },
            }]
        }]
    }

    project_meta = ProjectMeta(key='BACON')

    mock_jira_core.get_project_meta(project_meta)

    assert mock_jira_core._jira.createmeta.called
    assert project_meta.custom_fields == CustomFields(epic_name='10104')


def test_jira__get_project_meta__raises_project_doesnt_exist(mock_jira_core):
    '''
    Ensure ProjectDoesntExist exception is raised if nothing returned by API createmeta call
    '''
    # mock return from Jira createmeta API call
    mock_jira_core._jira.createmeta.return_value = {'projects': []}

    with pytest.raises(ProjectDoesntExist):
        mock_jira_core.get_project_meta(ProjectMeta(key='TEST'))


@mock.patch('jira_cli.main.jiraapi_object_to_issue', return_value=Issue.deserialize(ISSUE_1))
def test_jira__new_issue__removes_fields_which_cannot_be_posted_for_new_issue(mock_jiraapi_object_to_issue, mock_jira_core, project):
    '''
    Some fields cannot be posted to the Jira API. Ensure they are removed before the API call.
    '''
    # dont write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # jira.connect() returns the Jira connection for a given project
    mock_jira_core.connect.return_value = mock_jira_core._jira

    # add new issue to the jira object
    mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

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

    # assert "key" and "status" are removed
    mock_jira_core._jira.create_issue.assert_called_with(fields={'summary': 'A summary', 'issuetype': {'name': 'Story'}})


@pytest.mark.parametrize('error_msg,exception', [
    ('gh.epic.error.not.found', EpicNotFound),
    ("Field 'estimate' cannot be set", EstimateFieldUnavailable),
    ('cannot be set. It is not on the appropriate screen, or unknown.', JiraNotConfigured),
])
def test_jira__new_issue__raises_specific_exceptions(mock_jira_core, project, error_msg, exception):
    '''
    Ensure correct custom exception is raised when specific string found in Jira API error message
    '''
    # jira.connect() returns the Jira connection for a given project
    mock_jira_core.connect.return_value = mock_jira_core._jira

    # mock the Jira library to raise
    mock_jira_core._jira.create_issue.side_effect = mod_jira.JIRAError(text=error_msg)

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


@mock.patch('jira_cli.main.jiraapi_object_to_issue', return_value=Issue.deserialize(ISSUE_1))
def test_jira__new_issue__removes_temp_key_when_new_post_successful(mock_jiraapi_object_to_issue, mock_jira_core, project):
    '''
    Ensure a successful post of a new Issue deletes the old temp UUID key from self
    '''
    # dont write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # jira.connect() returns the Jira connection for a given project
    mock_jira_core.connect.return_value = mock_jira_core._jira

    # add new issue to the jira object
    mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

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

    # assert old local-only UUID temp key has been removed
    assert ISSUE_NEW['key'] not in mock_jira_core
    # assert new key returned from Jira API has been added (found in return from jiraapi_object_to_issue)
    assert ISSUE_1['key'] in mock_jira_core

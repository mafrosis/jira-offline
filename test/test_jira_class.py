'''
Tests for the Jira API class in main.py

Unlike other tests, these access the class directly, not via the mock_jira interface defined in
conftest.py
'''
from unittest import mock

import jira as mod_jira
import pytest

from fixtures import EPIC_1, ISSUE_1, ISSUE_MISSING_EPIC, ISSUE_NEW
from jira_cli.exceptions import EpicNotFound, EstimateFieldUnavailable, JiraNotConfigured
from jira_cli.models import Issue, ProjectMeta


@mock.patch('jira_cli.main.pull_issues')
@mock.patch('jira_cli.main.jsonlines')
@mock.patch('jira_cli.main.os')
def test_jira__load_issues__calls_pull_issues_when_cache_missing(mock_os, mock_jsonlines, mock_pull_issues, mock_jira_core):
    '''
    Ensure load_issues calls pull_issues when the cache file is missing
    '''
    # issues cache is missing
    mock_os.path.exists.return_value = False

    mock_jira_core.load_issues()

    assert mock_pull_issues.called


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
    result = mock_jira_core.get_project_meta('EGG')

    assert mock_jira_core.connect.called
    assert mock_jira_core._jira.createmeta.called
    assert result == ProjectMeta(name='Project EGG', issuetypes={'Epic', 'Party'})


@mock.patch('jira_cli.main.jiraapi_object_to_issue', return_value=Issue.deserialize(ISSUE_1))
def test_jira__new_issue__removes_fields_which_cannot_be_posted_for_new_issue(mock_jiraapi_object_to_issue, mock_jira_core):
    '''
    Some fields cannot be posted to the Jira API. Ensure they are removed before the API call.
    '''
    # dont write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # jira.connect() returns an instance of underlying Jira library
    mock_jira_core.connect.return_value = mock_jira_core._jira

    # add new issue to the jira object
    mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

    mock_jira_core.new_issue({
        'key': ISSUE_NEW['key'], 'status': 'Backlog', 'summary': 'A summary', 'issuetype': {'name': 'Story'}
    })

    # assert "key" and "status" are removed
    mock_jira_core._jira.create_issue.assert_called_with(fields={'summary': 'A summary', 'issuetype': {'name': 'Story'}})


@pytest.mark.parametrize('error_msg,exception', [
    ('gh.epic.error.not.found', EpicNotFound),
    ("Field 'estimate' cannot be set", EstimateFieldUnavailable),
    ('cannot be set. It is not on the appropriate screen, or unknown.', JiraNotConfigured),
])
def test_jira__new_issue__raises_specific_exceptions(mock_jira_core, error_msg, exception):
    '''
    Ensure correct custom exception is raised when specific string found in Jira API error message
    '''
    # jira.connect() returns an instance of underlying Jira library
    mock_jira_core.connect.return_value = mock_jira_core._jira

    # mock the Jira library to raise
    mock_jira_core._jira.create_issue.side_effect = mod_jira.JIRAError(text=error_msg)

    with pytest.raises(exception):
        mock_jira_core.new_issue({
            'key': ISSUE_NEW['key'], 'status': 'Backlog', 'summary': 'A summary', 'issuetype': {'name': 'Story'}
        })


@mock.patch('jira_cli.main.jiraapi_object_to_issue', return_value=Issue.deserialize(ISSUE_1))
def test_jira__new_issue__removes_temp_key_when_new_post_successful(mock_jiraapi_object_to_issue, mock_jira_core):
    '''
    Ensure a successful post of a new Issue deletes the old temp UUID key from self
    '''
    # dont write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # jira.connect() returns an instance of underlying Jira library
    mock_jira_core.connect.return_value = mock_jira_core._jira

    # add new issue to the jira object
    mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

    mock_jira_core.new_issue({
        'key': ISSUE_NEW['key'], 'status': 'Backlog', 'summary': 'A summary', 'issuetype': {'name': 'Story'}
    })

    # assert old local-only UUID temp key has been removed
    assert ISSUE_NEW['key'] not in mock_jira_core
    # assert new key returned from Jira API has been added (found in return from jiraapi_object_to_issue)
    assert ISSUE_1['key'] in mock_jira_core

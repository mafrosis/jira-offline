'''
Tests for the Jira API class in main.py

Unlike other tests, these access the class directly, not via the mock_jira interface defined in
conftest.py
'''
import copy
from unittest import mock

import pandas as pd
import pytest

from fixtures import EPIC_1, ISSUE_1, ISSUE_2, ISSUE_MISSING_EPIC, ISSUE_NEW
from helpers import compare_issue_helper, setup_jira_dataframe_helper
from jira_offline.exceptions import (EpicNotFound, FailedAuthError, JiraApiError, JiraNotConfigured,
                                     ProjectDoesntExist)
from jira_offline.models import Issue, IssueType, ProjectMeta


def test_jira__mutablemapping__get_item__(mock_jira_core, project):
    '''
    Ensure that __get_item__ returns a valid Issue object from the underlying dataframe
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=project)
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

    # retrieve the issue via __get_item__
    retrieved_issue = mock_jira_core['TEST-71']

    compare_issue_helper(issue_1, retrieved_issue)


def test_jira__mutablemapping__set_item__new(mock_jira_core, project):
    '''
    Ensure that __set_item__ adds a valid new Issue to the underlying dataframe
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=project)
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

    assert len(mock_jira_core._df) == 1

    # create another Issue fixture
    issue_2 = Issue.deserialize(ISSUE_2, project=project)

    # add the issue via __set_item__
    mock_jira_core['TEST-72'] = issue_2

    assert len(mock_jira_core._df) == 2

    compare_issue_helper(issue_2, mock_jira_core['TEST-72'])


def test_jira__mutablemapping__set_item__overwrite(mock_jira_core, project):
    '''
    Ensure that __set_item__ overwrites an existing Issue to the underlying dataframe
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=project)
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

    assert len(mock_jira_core._df) == 1

    # add the issue via __set_item__
    mock_jira_core['TEST-71'] = issue_1

    assert len(mock_jira_core._df) == 1

    compare_issue_helper(issue_1, mock_jira_core['TEST-71'])


def test_jira__mutablemapping__del_item__(mock_jira_core, project):
    '''
    Ensure that __del_item__ deletes an issue from the underlying dataframe
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project=project)

    # Setup the Jira DataFrame
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

    assert len(mock_jira_core._df) == 1

    # delete the issue via __del_item__
    del mock_jira_core['TEST-71']

    assert len(mock_jira_core._df) == 0


def test_jira__mutablemapping__in_operator(mock_jira_core, project):
    '''
    Ensure that one can use the "in" operator with the Jira dict
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project=project)

    # Setup the Jira DataFrame
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

    # simply assert the key is in the dict
    assert ISSUE_1['key'] in mock_jira_core


def test_jira__mutablemapping__in_operator_with_new_issue(mock_jira_core, project):
    '''
    Ensure that one can use the "in" operator with the Jira dict
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=project)
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

    mock_jira_core['7242cc9e-ea52-4e51-bd84-2ced250cabf0'] = Issue.deserialize(ISSUE_NEW)

    # simply assert the key is in the dict
    assert '7242cc9e-ea52-4e51-bd84-2ced250cabf0' in mock_jira_core


@pytest.mark.parametrize('issue_fixture', [ISSUE_1, ISSUE_2, ISSUE_NEW, EPIC_1])
def test_jira__mutablemapping__roundtrip(mock_jira, project, issue_fixture):
    '''
    Ensure an issue can be set into the Jira object and be recreated without change.
    Parameterized with the various different types of Issue fixtures.
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_MISSING_EPIC, project=project)
    mock_jira._df = setup_jira_dataframe_helper([issue_1])

    key = issue_fixture['key']

    # add to dataframe (via __set_item__)
    mock_jira[key] = issue_1 = Issue.deserialize(issue_fixture, project=project)

    # extract back out of dataframe (via __get_item__)
    issue_2 = mock_jira[key]

    compare_issue_helper(issue_1, issue_2)
    assert issue_1.original == issue_2.original


def test_jira__mutablemapping__roundtrip_with_mod(mock_jira, project):
    '''
    Ensure an issue can be set into the Jira object, and be recreated and then modified
    '''
    # add to dataframe (via __set_item__)
    mock_jira['TEST-71'] = issue_1 = Issue.deserialize(ISSUE_1, project=project)

    # extract back out of dataframe (via __get_item__)
    issue_2 = mock_jira['TEST-71']

    with mock.patch('jira_offline.jira.jira', mock_jira):
        setattr(issue_2, 'summary', 'egg')

    assert issue_1.summary == 'This is the story summary'
    assert issue_2.summary == 'egg'
    assert issue_1.modified is False
    assert issue_2.modified is True
    assert issue_1.original == issue_2.original


@mock.patch('jira_offline.jira.get_cache_filepath', return_value='filepath')
@mock.patch('jira_offline.jira.pd', autospec=True)
@mock.patch('jira_offline.jira.os')
def test_jira__load_issues__calls_read_feather_when_cache_file_exists(mock_os, mock_pandas, mock_get_cache_filepath, mock_jira_core):
    '''
    Ensure pd.read_feather is called when the cache file exists
    '''
    # issues cache is present, and non-zero in size
    mock_os.path.exists.return_value = True
    mock_os.stat.return_value.st_size = 1

    mock_jira_core.load_issues()

    mock_pandas.read_feather.assert_called_once_with('filepath')


@mock.patch('jira_offline.jira.get_cache_filepath', return_value='filepath')
@mock.patch('jira_offline.jira.pd', autospec=True)
@mock.patch('jira_offline.jira.os')
def test_jira__load_issues__reads_disk_only_once(mock_os, mock_pandas, mock_get_cache_filepath, mock_jira_core):
    '''
    Ensure pd.read_feather is called when the cache file exists
    '''
    # issues cache is present, and non-zero in size
    mock_os.path.exists.return_value = True
    mock_os.stat.return_value.st_size = 1

    # method `_expand_customfields` returns the final DataFrame
    mock_jira_core._expand_customfields = mock.Mock()
    mock_jira_core._expand_customfields.return_value = pd.DataFrame({'key': ['egg'], 'val': [0]})

    mock_jira_core.load_issues()
    assert mock_pandas.read_feather.call_count == 1

    mock_jira_core.load_issues()
    assert mock_pandas.read_feather.call_count == 1


@mock.patch('jira_offline.jira.pd', autospec=True)
@mock.patch('jira_offline.jira.os')
def test_jira__load_issues__DOES_NOT_call_read_feather_when_cache_file_missing(mock_os, mock_pandas, mock_jira_core):
    '''
    Ensure pd.read_feather is NOT called when the cache file DOESNT exist
    '''
    # issues cache is missing
    mock_os.path.exists.return_value = False

    mock_jira_core.load_issues()

    assert not mock_pandas.read_feather.called


@pytest.mark.parametrize('issue_fixture', [ISSUE_1, ISSUE_2, ISSUE_NEW, EPIC_1])
@mock.patch('jira_offline.jira.os')
def test_jira__write_issues_load_issues__roundtrip(mock_os, mock_jira_core, project, tmpdir, issue_fixture):
    '''
    Validate that pd.write_feather followed by pd.read_feather does not cause an error.
    Include only existing issues (ie. those which already exist on Jira)

    NOTE: This test writes to disk necessarily
    '''
    # issues cache is present, and non-zero in size
    mock_os.path.exists.return_value = True
    mock_os.stat.return_value.st_size = 1

    # Setup the Jira DataFrame
    issue = Issue.deserialize(issue_fixture, project=project)
    mock_jira_core._df = setup_jira_dataframe_helper([issue])

    key = issue_fixture['key']

    with mock.patch('jira_offline.jira.get_cache_filepath', return_value=f'{tmpdir}/issues.feather'):
        mock_jira_core.write_issues()

        compare_issue_helper(issue, mock_jira_core[key])

        mock_jira_core.load_issues()

        compare_issue_helper(issue, mock_jira_core[key])

        # ensure the original field is added during load_issues()
        assert 'original' in mock_jira_core._df.columns


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__overrides_default_timezone_when_set(mock_api_get, mock_jira_core, project):
    '''
    Ensure get_project_meta() method overrides ProjectMeta.timezone default when returned from a
    user's profile.

    The default is the end-user's local system timezone, set in ProjectMeta.factory()
    '''
    # mock out call to _get_project_issue_statuses and _get_project_components
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()
    mock_jira_core._get_user_timezone = mock.Mock(return_value='America/New_York')

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

    assert project.timezone.zone == project.timezone.zone

    mock_jira_core.get_project_meta(project)

    assert project.timezone.zone == 'America/New_York'


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
                        'fieldId': 'customfield_10104',
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


@pytest.mark.parametrize('jira_ref', [
    ('fieldId'),
    ('key'),
])
@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__extracts_locked_customfield(mock_api_get, mock_jira_core, project, jira_ref):
    '''
    Ensure get_project_meta() method extracts the Jira-provided "locked" customfield for a project

    The parameterization covers the scenario where Jira Cloud uses the fieldname "key", but Jira
    Server uses "fieldId"
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
                    'customfield_10200': {
                        jira_ref: 'customfield_10200',
                        'name': 'Epic Name',
                    },
                },
            }]
        }]
    }

    mock_jira_core.get_project_meta(project)

    assert mock_api_get.called
    assert project.customfields.epic_name == 'customfield_10200'


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


def test_jira__load_customfields__extracts_locked_customfield(mock_jira_core, project):
    '''
    Ensure _load_customfields() method extracts the Jira-provided "locked" customfield for a project
    '''
    # Fixture for partial return from Jira createmeta API
    issuetypes_fixture = [{
        'self': 'https://example.com/rest/api/2/issuetype/5',
        'id': '5',
        'name': 'Epic',
        'fields': {
            'summary': {
                'name': 'Summary'
            },
            'customfield_10200': {
                'fieldId': 'customfield_10200',
                'name': 'Epic Name',
            },
        },
    }]

    mock_jira_core._load_customfields(project, issuetypes_fixture)

    assert project.customfields.epic_name == 'customfield_10200'


@pytest.mark.parametrize('customfield_id,customfield_value', [
    ('story-points', 'customfield_10300'),
    ('story_points', 'customfield_10300'),
])
def test_jira__load_customfields__predefined_customfield(mock_jira_core, customfield_id, customfield_value):
    '''
    Ensure _load_customfields() method extracts known user-specified customfield for a project
    '''
    # Fixture for partial return from Jira createmeta API
    issuetypes_fixture = [{
        'self': 'https://example.com/rest/api/2/issuetype/5',
        'id': '5',
        'name': 'Epic',
        'fields': {
            'summary': {
                'name': 'Summary'
            },
            'customfield_10200': {
                'fieldId': 'customfield_10200',
                'name': 'Epic Name',
            },
            'customfield_10300': {
                'fieldId': 'customfield_10300',
                'name': 'Story Points',
            },
        },
    }]

    # Setup app config as extracted from jira-offline.ini
    mock_jira_core.config.customfields = {
        '*': {customfield_id: customfield_value},
    }

    project = ProjectMeta(key='TEST')

    mock_jira_core._load_customfields(project, issuetypes_fixture)

    assert project.customfields.epic_name == 'customfield_10200'
    assert project.customfields.story_points == 'customfield_10300'


def test_jira__load_customfields__user_defined_customfield_for_all_projects(mock_jira_core):
    '''
    Ensure _load_customfields() method extracts arbitrary user-defined customfields which apply to
    all projects
    '''
    # Fixture for partial return from Jira createmeta API
    issuetypes_fixture = [{
        'self': 'https://example.com/rest/api/2/issuetype/5',
        'id': '5',
        'name': 'Epic',
        'fields': {
            'summary': {
                'name': 'Summary'
            },
            'customfield_10400': {
                'fieldId': 'customfield_10400',
                'name': 'Arbitrary User-Defined Field',
            },
        },
    }]

    # Setup app config as extracted from jira-offline.ini
    mock_jira_core.config.customfields = {
        '*': {'arbitrary-user-defined-field': 'customfield_10400'},
    }

    project1 = ProjectMeta(key='TEST1')
    project2 = ProjectMeta(key='TEST2')

    mock_jira_core._load_customfields(project1, issuetypes_fixture)
    mock_jira_core._load_customfields(project2, issuetypes_fixture)

    assert project1.customfields.extended['arbitrary_user_defined_field'] == 'customfield_10400'
    assert project2.customfields.extended['arbitrary_user_defined_field'] == 'customfield_10400'


def test_jira__load_customfields__user_defined_customfield_for_projects_on_host(mock_jira_core):
    '''
    Ensure _load_customfields() method extracts arbitrary user-defined customfields which apply to
    projects on a single Jira host only
    '''
    # Fixture for partial return from Jira createmeta API
    issuetypes_fixture = [{
        'self': 'https://example.com/rest/api/2/issuetype/5',
        'id': '5',
        'name': 'Epic',
        'fields': {
            'summary': {
                'name': 'Summary'
            },
            'customfield_10400': {
                'fieldId': 'customfield_10400',
                'name': 'Arbitrary User-Defined Field',
            },
        },
    }]

    # Setup app config as extracted from jira-offline.ini
    mock_jira_core.config.customfields = {
        'jira.example.com': {'arbitrary-user-defined-field': 'customfield_10400'},
    }

    project1 = ProjectMeta(key='TEST1', hostname='jira.example.com')
    project2 = ProjectMeta(key='TEST2', hostname='notjira.example.com')

    mock_jira_core._load_customfields(project1, issuetypes_fixture)
    mock_jira_core._load_customfields(project2, issuetypes_fixture)

    assert project1.customfields.extended['arbitrary_user_defined_field'] == 'customfield_10400'
    assert 'arbitrary_user_defined_field' not in project2.customfields.extended


def test_jira__load_customfields__project_specific_customfield_overrides_all_projects(mock_jira_core):
    '''
    Ensure _load_customfields() overrides general all-project customfields config with host-specific
    Jira customfields
    '''
    # Fixture for partial return from Jira createmeta API
    issuetypes_fixture = [{
        'self': 'https://example.com/rest/api/2/issuetype/5',
        'id': '5',
        'name': 'Epic',
        'fields': {
            'summary': {
                'name': 'Summary'
            },
            'customfield_10400': {
                'fieldId': 'customfield_10400',
                'name': 'Arbitrary User-Defined Field 1',
            },
            'customfield_10999': {
                'fieldId': 'customfield_10999',
                'name': 'Arbitrary User-Defined Field 2',
            },
        },
    }]

    # Setup app config as extracted from jira-offline.ini
    mock_jira_core.config.customfields = {
        '*': {'custom1': 'customfield_10400'},
        'jira.example.com': {'custom1': 'customfield_10999'},
    }

    project1 = ProjectMeta(key='TEST1', hostname='jira.example.com')
    project2 = ProjectMeta(key='TEST2', hostname='notjira.example.com')

    mock_jira_core._load_customfields(project1, issuetypes_fixture)
    mock_jira_core._load_customfields(project2, issuetypes_fixture)

    assert project1.customfields.extended['custom1'] == 'customfield_10999'
    assert project2.customfields.extended['custom1'] == 'customfield_10400'


@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__removes_fields_which_cannot_be_posted_for_new_issue(
        mock_api_post, mock_jira_core, project
    ):
    '''
    Some fields cannot be posted to the Jira API. Ensure they are removed before the API call.
    '''
    # Setup the the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=project)
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

    # dont write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # add new issue to the jira object
    mock_jira_core[ISSUE_NEW['key']] = Issue.deserialize(ISSUE_NEW)

    # mock the fetch_issue() call that happens after successful new_issue() call
    mock_jira_core.fetch_issue = mock.Mock(return_value=Issue.deserialize(ISSUE_1))

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
    # Setup the the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=project)
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1])

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
def test_jira__fetch_issue__returns_output_from_jiraapi_object_to_issue(
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


def test_jira__keys__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.keys() respects a filter set in jira.filter
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=ProjectMeta('FIRST'))
    issue_2 = Issue.deserialize(ISSUE_2, project=ProjectMeta('SECOND'))
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1, issue_2])

    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        assert list(mock_jira_core.keys()) == ['TEST-71', 'TEST-72']

        mock_jira_core.filter.set('project = SECOND')

        assert list(mock_jira_core.keys()) == ['TEST-72']


def test_jira__values__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.values() respects a filter set in jira.filter
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=ProjectMeta('FIRST'))
    issue_2 = Issue.deserialize(ISSUE_2, project=ProjectMeta('SECOND'))
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1, issue_2])

    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        assert list(mock_jira_core.values()) == [mock_jira_core['TEST-71'], mock_jira_core['TEST-72']]

        mock_jira_core.filter.set('project = SECOND')

        assert list(mock_jira_core.values()) == [mock_jira_core['TEST-72']]


def test_jira__items__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.items() respects a filter set in jira.filter
    '''
    # Setup the Jira DataFrame
    issue_1 = Issue.deserialize(ISSUE_1, project=ProjectMeta('FIRST'))
    issue_2 = Issue.deserialize(ISSUE_2, project=ProjectMeta('SECOND'))
    mock_jira_core._df = setup_jira_dataframe_helper([issue_1, issue_2])

    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        assert list(mock_jira_core.items()) == [
            ('TEST-71', mock_jira_core['TEST-71']),
            ('TEST-72', mock_jira_core['TEST-72']),
        ]

        mock_jira_core.filter.set('project = SECOND')

        assert list(mock_jira_core.items()) == [
            ('TEST-72', mock_jira_core['TEST-72']),
        ]


def test_jira__update__merge_new_issues_into_empty_dataframe(mock_jira, project):
    '''
    Ensure list of Issues can be appended without error when the cache is empty
    '''
    # output from sync.pull_single_project
    incoming_issues = [
        Issue.deserialize(ISSUE_1, project),
        Issue.deserialize(ISSUE_2, project),
    ]

    assert len(mock_jira) == 0

    mock_jira.update(incoming_issues)

    assert len(mock_jira) == 2

    compare_issue_helper(incoming_issues[0], mock_jira['TEST-71'])
    compare_issue_helper(incoming_issues[1], mock_jira['TEST-72'])


def test_jira__update__merge_new_issues_into_existing_dataframe(mock_jira, project):
    '''
    Ensure list of Issues can be appended without error when issues are already in the cache
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project=project)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1])

    # output from sync.pull_single_project
    incoming_issues = [
        Issue.deserialize(ISSUE_2, project),
        Issue.deserialize(EPIC_1, project),
    ]

    assert len(mock_jira) == 1

    mock_jira.update(incoming_issues)

    assert len(mock_jira) == 3

    compare_issue_helper(issue_1, mock_jira['TEST-71'])
    compare_issue_helper(incoming_issues[0], mock_jira['TEST-72'])
    compare_issue_helper(incoming_issues[1], mock_jira['TEST-1'])


def test_jira__update__merge_existing_issues_into_existing_dataframe(mock_jira, project):
    '''
    Ensure list of Issues can be updated in-place without error when the issues already in the cache
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project=project)
    issue_2 = Issue.deserialize(ISSUE_2, project=project)

    # Setup the Jira DataFrame
    mock_jira._df = setup_jira_dataframe_helper([issue_1, issue_2])

    # change some fields for the update
    ISSUE_1_MODIFIED = copy.deepcopy(ISSUE_1)
    ISSUE_1_MODIFIED['summary'] = 'Updated summary 1'
    ISSUE_2_MODIFIED = copy.deepcopy(ISSUE_2)
    ISSUE_2_MODIFIED['summary'] = 'Updated summary 2'

    # output from sync.pull_single_project
    incoming_issues = [
        Issue.deserialize(ISSUE_1_MODIFIED, project),
        Issue.deserialize(ISSUE_2_MODIFIED, project),
    ]

    assert len(mock_jira) == 2

    mock_jira.update(incoming_issues)

    assert len(mock_jira) == 2

    compare_issue_helper(incoming_issues[0], mock_jira['TEST-71'])
    compare_issue_helper(incoming_issues[1], mock_jira['TEST-72'])

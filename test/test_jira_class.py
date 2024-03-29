'''
Tests for the Jira API class in main.py

Unlike other tests, these access the class directly, not via the mock_jira interface defined in
conftest.py
'''
from unittest import mock

import pandas as pd
import pytest

from fixtures import EPIC_1, EPIC_NEW, ISSUE_1, ISSUE_NEW
from helpers import compare_issue_helper
from jira_offline.exceptions import FailedAuthError, JiraApiError, ProjectDoesntExist
from jira_offline.models import Issue, IssueType, IssueUpdate, ProjectMeta


def test_jira__mutablemapping__getitem__(mock_jira_core, project):
    '''
    Ensure that __getitem__ returns a valid Issue object from the underlying DataFrame
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    # Retrieve the issue via __getitem__
    retrieved_issue = mock_jira_core['TEST-71']

    compare_issue_helper(issue_1, retrieved_issue)


@pytest.mark.parametrize('key', [
    '7242cc9e-ea52-4e51-bd84-2ced250cabf0',
    '7242cc9e',
])
def test_jira__mutablemapping__getitem__handles_abbrev_key(mock_jira_core, project, key):
    '''
    Ensure that __getitem__ returns a valid Issue object from the underlying DataFrame, when passed
    an abbreviated UUID key from a new Issue
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_new = Issue.deserialize(ISSUE_NEW, project)
        issue_new.commit()

    # Retrieve the issue via __getitem__
    retrieved_issue = mock_jira_core[key]

    compare_issue_helper(issue_new, retrieved_issue)


def test_jira__mutablemapping__setitem__new(mock_jira_core, project):
    '''
    Ensure that __setitem__ adds a valid new Issue to the underlying DataFrame
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    assert len(mock_jira_core._df) == 1

    # create another Issue fixture
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)

    # add the issue via __setitem__
    mock_jira_core['TEST-72'] = issue_2

    assert len(mock_jira_core._df) == 2

    compare_issue_helper(issue_2, mock_jira_core['TEST-72'])


def test_jira__mutablemapping__setitem__overwrite(mock_jira_core, project):
    '''
    Ensure that __setitem__ overwrites an existing Issue in the underlying DataFrame
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    assert len(mock_jira_core._df) == 1

    # add the issue via __setitem__
    mock_jira_core['TEST-71'] = issue_1

    assert len(mock_jira_core._df) == 1

    compare_issue_helper(issue_1, mock_jira_core['TEST-71'])


def test_jira__mutablemapping__delitem__(mock_jira_core, project):
    '''
    Ensure that __delitem__ deletes an issue from the underlying DataFrame
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    assert len(mock_jira_core._df) == 1

    # delete the issue via __delitem__
    del mock_jira_core['TEST-71']

    assert len(mock_jira_core._df) == 0


@pytest.mark.parametrize('key', [
    '7242cc9e-ea52-4e51-bd84-2ced250cabf0',
    '7242cc9e',
])
def test_jira__mutablemapping__contains__handles_abbrev_key(mock_jira_core, project, key):
    '''
    Ensure that __contains__ returns True when passed a valid abbreviated UUID key from a new Issue
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_new = Issue.deserialize(ISSUE_NEW, project)
        issue_new.commit()

    # Check dictionary __contains__
    assert key in mock_jira_core


def test_jira__mutablemapping__in_operator(mock_jira_core, project):
    '''
    Ensure that one can use the "in" operator with the Jira dict
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    # simply assert the key is in the dict
    assert ISSUE_1['key'] in mock_jira_core


def test_jira__mutablemapping__in_operator_with_new_issue(mock_jira_core, project):
    '''
    Ensure that one can use the "in" operator with the Jira dict
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    mock_jira_core['7242cc9e-ea52-4e51-bd84-2ced250cabf0'] = Issue.deserialize(ISSUE_NEW, project)

    # simply assert the key is in the dict
    assert '7242cc9e-ea52-4e51-bd84-2ced250cabf0' in mock_jira_core


@pytest.mark.parametrize('issue_fixture', [
    ISSUE_1,
    ISSUE_NEW,
    EPIC_1,
])
def test_jira__mutablemapping__roundtrip(mock_jira, project, issue_fixture):
    '''
    Ensure an issue can be set into the Jira object and be recreated without change.

    Parameterized with the various different types of Issue fixtures.
    '''
    # add to dataframe (via __setitem__)
    mock_jira[issue_fixture['key']] = issue_1 = Issue.deserialize(issue_fixture, project)

    # extract back out of dataframe (via __get_item__)
    issue_2 = mock_jira[issue_fixture['key']]

    compare_issue_helper(issue_1, issue_2)
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


@pytest.mark.parametrize('issue_fixture', [ISSUE_1, ISSUE_NEW, EPIC_1])
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

    # Create parameterized issue fixture
    issue_1 = Issue.deserialize(issue_fixture, project)

    # Create a modified issue
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)
        issue_2.assignee = 'dave'

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1.commit()
        issue_2.commit()

    key = issue_fixture['key']

    with mock.patch('jira_offline.jira.get_cache_filepath', return_value=f'{tmpdir}/issues.feather'):
        mock_jira_core.write_issues()

        compare_issue_helper(issue_1, mock_jira_core[key])
        compare_issue_helper(issue_2, mock_jira_core['TEST-72'])

        mock_jira_core.load_issues()

        compare_issue_helper(issue_1, mock_jira_core[key])
        compare_issue_helper(issue_2, mock_jira_core['TEST-72'])

        # ensure the original field is added during load_issues()
        assert 'original' in mock_jira_core._df.columns


@mock.patch('jira_offline.jira.os')
def test_jira__expand_customfields__replaces_extended_columns(mock_os, mock_jira_core, project):
    '''
    Validate `_expand_customfields` removes existing extended columns and loads new ones from the
    "extended" column in the DataFrame.
    '''
    # Create a test DataFrame
    df_test = pd.DataFrame({
        'key': [1, 2],
        'extended': [{'a': 'x', 'b': None}, {'a': None, 'b': 'y'}],
        'extended.rm': [3, 4],
    }).set_index('key')

    df = mock_jira_core._expand_customfields(df_test)

    # Validate previous extended column was dropped
    assert 'extended.rm' not in df.columns

    # Validate "a" and "b" keys in the extended column's dict are expanded into DataFrame columns
    assert df.loc[1, 'extended.a'] == 'x'
    assert df.loc[1, 'extended.b'] == ''
    assert df.loc[2, 'extended.a'] == ''
    assert df.loc[2, 'extended.b'] == 'y'


@mock.patch('jira_offline.jira.os')
def test_jira__contract_customfields__cleans_extended_fields_where_all_set_to_none(mock_os, mock_jira_core, project):
    '''
    Validate that `_contract_customfields` removes all extended value which are None for all issues.
    '''
    # Create a test DataFrame
    df_test = pd.DataFrame({
        'key': [1, 2],
        'extended': [{'a': 'x', 'b': None}, {'a': None, 'b': None}],
        'extended.rm': [3, 4],
    }).set_index('key')

    df = mock_jira_core._contract_customfields(df_test)

    # Validate previous extended column was dropped
    assert 'extended.rm' not in df.columns

    # Validate only "a" remains in extended column
    assert df.loc[1, 'extended'] == {'a': 'x'}
    assert df.loc[2, 'extended'] == {'a': None}


@mock.patch('jira_offline.jira.apply_user_config_to_project')
@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__calls_apply_user_config(
        mock_api_get, mock_apply_user_config_to_project, mock_jira_core, project
    ):
    '''
    Ensure get_project_meta() method calls apply_user_config_to_project()
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
            'issuetypes': []
        }]
    }

    mock_jira_core.get_project_meta(project)

    assert mock_apply_user_config_to_project.called


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__overrides_default_timezone_when_set(mock_api_get, mock_jira_core, timezone_project):
    '''
    Ensure get_project_meta() method overrides ProjectMeta.timezone default when returned from a
    user's profile.

    The default is the end-user's local system timezone, set in ProjectMeta.factory()
    '''
    # mock out calls to helpers which hit Jira API
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()
    mock_jira_core._get_sprints = mock.Mock()

    # Mock a specific timezone
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

    assert timezone_project.timezone.zone == timezone_project.timezone.zone

    mock_jira_core.get_project_meta(timezone_project)

    assert timezone_project.timezone.zone == 'America/New_York'


@mock.patch('jira_offline.jira.api_get')
def test_jira__get_project_meta__extracts_priorities(mock_api_get, mock_jira_core, project):
    '''
    Ensure get_project_meta() method extracts project priorities from a project
    '''
    # mock out calls to helpers which hit Jira API
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()
    mock_jira_core._get_sprints = mock.Mock()

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
    # mock out calls to helpers which hit Jira API
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()
    mock_jira_core._get_sprints = mock.Mock()

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
    # mock out calls to helpers which hit Jira API
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()
    mock_jira_core._get_sprints = mock.Mock()

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
    # mock out calls to helpers which hit Jira API
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()
    mock_jira_core._get_sprints = mock.Mock()

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
    # mock out calls to helpers which hit Jira API
    mock_jira_core._get_project_issue_statuses = mock.Mock()
    mock_jira_core._get_project_components = mock.Mock()
    mock_jira_core._get_sprints = mock.Mock()

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
    mock_jira_core.config.user_config.customfields = {
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
    mock_jira_core.config.user_config.customfields = {
        '*': {'arbitrary-user-defined-field': 'customfield_10400'},
    }

    project_1 = ProjectMeta(key='TEST1')
    project_2 = ProjectMeta(key='TEST2')

    mock_jira_core._load_customfields(project_1, issuetypes_fixture)
    mock_jira_core._load_customfields(project_2, issuetypes_fixture)

    assert project_1.customfields.extended['arbitrary_user_defined_field'] == 'customfield_10400'
    assert project_2.customfields.extended['arbitrary_user_defined_field'] == 'customfield_10400'


@pytest.mark.parametrize('target', [
    ('jira.example.com'),
    ('TEST1'),
])
def test_jira__load_customfields__user_defined_customfield_for_specific_projects(mock_jira_core, target):
    '''
    Ensure _load_customfields() method extracts arbitrary user-defined customfields which apply to
    single project only, or projects on a single Jira host only
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
    mock_jira_core.config.user_config.customfields = {
        target: {'arbitrary-user-defined-field': 'customfield_10400'},
    }

    project_1 = ProjectMeta(key='TEST1', hostname='jira.example.com')
    project_2 = ProjectMeta(key='TEST2', hostname='notjira.example.com')

    mock_jira_core._load_customfields(project_1, issuetypes_fixture)
    mock_jira_core._load_customfields(project_2, issuetypes_fixture)

    assert project_1.customfields.extended['arbitrary_user_defined_field'] == 'customfield_10400'
    assert 'arbitrary_user_defined_field' not in project_2.customfields.extended


def test_jira__load_customfields__jira_host_specific_customfield_overrides_global(mock_jira_core):
    '''
    Ensure _load_customfields() overrides global customfields with Jira-host specific customfields
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
            'customfield_10500': {
                'fieldId': 'customfield_10500',
                'name': 'Arbitrary User-Defined Field 2',
            },
        },
    }]

    # Setup app config as extracted from jira-offline.ini
    mock_jira_core.config.user_config.customfields = {
        'jira.example.com': {'custom1': 'customfield_10500'},
        '*': {'custom1': 'customfield_10400'},
    }

    project_1 = ProjectMeta(key='TEST1', hostname='jira.example.com')

    mock_jira_core._load_customfields(project_1, issuetypes_fixture)

    assert project_1.customfields.extended['custom1'] == 'customfield_10500'


def test_jira__load_customfields__project_specific_customfield_overrides_global(mock_jira_core):
    '''
    Ensure _load_customfields() overrides global customfields with project specific customfields
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
            'customfield_10500': {
                'fieldId': 'customfield_10500',
                'name': 'Arbitrary User-Defined Field 2',
            },
        },
    }]

    # Setup app config as extracted from jira-offline.ini
    mock_jira_core.config.user_config.customfields = {
        'TEST3': {'custom1': 'customfield_10500'},
        '*': {'custom1': 'customfield_10400'},
    }

    project_1 = ProjectMeta(key='TEST3', hostname='jira.example.com')

    mock_jira_core._load_customfields(project_1, issuetypes_fixture)

    assert project_1.customfields.extended['custom1'] == 'customfield_10500'


def test_jira__load_customfields__project_specific_customfield_overrides_host_specific(mock_jira_core):
    '''
    Ensure _load_customfields() overrides global customfields with project specific customfields
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
            'customfield_10500': {
                'fieldId': 'customfield_10500',
                'name': 'Arbitrary User-Defined Field 2',
            },
            'customfield_10600': {
                'fieldId': 'customfield_10600',
                'name': 'Arbitrary User-Defined Field 3',
            },
        },
    }]

    # Setup app config as extracted from jira-offline.ini
    mock_jira_core.config.user_config.customfields = {
        'TEST3': {'custom1': 'customfield_10600'},
        'jira.example.com': {'custom1': 'customfield_10500'},
    }

    project_1 = ProjectMeta(key='TEST3', hostname='jira.example.com')

    mock_jira_core._load_customfields(project_1, issuetypes_fixture)

    assert project_1.customfields.extended['custom1'] == 'customfield_10600'


@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__calls_write_issues_on_success(mock_api_post, mock_jira_core, project):
    '''
    Ensure a successful new issue API request causes call to write_issues and returns the new Issue
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_new = Issue.deserialize(ISSUE_NEW, project)
        issue_new.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # Mock the return from fetch_issue() which happens after a successful new_issue() call
    issue_1 = Issue.deserialize(ISSUE_1, project)
    mock_jira_core.fetch_issue = mock.Mock(return_value=issue_1)

    updated_issue = mock_jira_core.new_issue(
        project,
        fields={
            'project': {'id': project.jira_id},
            'summary': 'A summary',
            'issuetype': {'name': 'Story'},
        },
        offline_temp_key=issue_new.key,
    )

    assert updated_issue is issue_1
    assert mock_jira_core.fetch_issue.called
    assert mock_jira_core.write_issues.called


@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__does_not_call_write_issues_on_failure(mock_api_post, mock_jira_core, project):
    '''
    Ensure a failed new issue API request does not cause call to write_issues
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_new = Issue.deserialize(ISSUE_NEW, project)
        issue_new.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # Mock api_post() to raise an exception, and mock jira.fetch_issue
    mock_api_post.side_effect = [JiraApiError]
    mock_jira_core.fetch_issue = mock.Mock()

    updated_issue = None

    with pytest.raises(JiraApiError):
        updated_issue = mock_jira_core.new_issue(
            project,
            fields={
                'project': {'id': project.jira_id},
                'summary': 'A summary',
                'issuetype': {'name': 'Story'},
            },
            offline_temp_key=issue_new.key,
        )

    assert updated_issue is None
    assert not mock_jira_core.fetch_issue.called
    assert not mock_jira_core.write_issues.called


@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__removes_temp_key_when_new_post_successful(mock_api_post, mock_jira_core, project):
    '''
    Ensure a successful new Issue creation deletes the old temp UUID key
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_new = Issue.deserialize(ISSUE_NEW, project)
        issue_new.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # Mock the return from fetch_issue() which happens after a successful new_issue() call
    issue_1 = Issue.deserialize(ISSUE_1, project)
    mock_jira_core.fetch_issue = mock.Mock(return_value=issue_1)

    mock_jira_core.new_issue(
        project,
        fields={
            'project': {'id': project.jira_id},
            'summary': 'A summary',
            'issuetype': {'name': 'Story'},
        },
        offline_temp_key=issue_new.key,
    )

    # Assert new key returned from Jira API has been added
    assert issue_1.key in mock_jira_core
    # Assert temporary key has been removed
    assert issue_new.key not in mock_jira_core


@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__ignores_transitions(mock_api_post, mock_jira_core, project):
    '''
    Ensure new_issue method ignores "transitions" key passed in fields
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_new = Issue.deserialize(ISSUE_NEW, project)
        issue_new.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # Mock the return from fetch_issue() which happens after a successful new_issue() call
    issue_1 = Issue.deserialize(ISSUE_1, project)
    mock_jira_core.fetch_issue = mock.Mock(return_value=issue_1)

    mock_jira_core.new_issue(
        project,
        fields={
            'project': {'id': project.jira_id},
            'summary': 'A summary',
            'issuetype': {'name': 'Story'},
            'transitions': {'egg': 'bacon'},
        },
        offline_temp_key=issue_new.key,
    )

    # Assert new key returned from Jira API has been added
    assert 'transitions' not in mock_api_post.call_args_list[0][1]['data']['fields']


@pytest.mark.parametrize('link_name', [
    'epic_link',
    'parent_link'
])
@mock.patch('jira_offline.jira.api_post')
def test_jira__new_issue__link_is_updated_after_post(mock_api_post, mock_jira_core, project, link_name):
    '''
    Ensure that "Parent Link" and "Epic Link" are updated to the new parent key
    '''
    with mock.patch.dict(ISSUE_NEW, {link_name: EPIC_NEW['key']}):
        issue_new = Issue.deserialize(ISSUE_NEW, project)

    epic_new = Issue.deserialize(EPIC_NEW, project)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_new.commit()
        epic_new.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # Mock the return from fetch_issue() which happens after a successful new_issue() call
    epic_1 = Issue.deserialize(EPIC_1, project)
    mock_jira_core.fetch_issue = mock.Mock(return_value=epic_1)

    # Validate the link value before the call to new_issue
    assert getattr(mock_jira_core[ISSUE_NEW['key']], link_name) == epic_new.key

    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        # Simulated post of the epic for issue creation
        mock_jira_core.new_issue(
            project,
            fields={
                'project': {'id': project.jira_id},
                'summary': 'A summary',
                'issuetype': {'name': 'Epic'},
            },
            offline_temp_key=epic_new.key,
        )

    # Validate the link value has been updated
    assert getattr(mock_jira_core[ISSUE_NEW['key']], link_name) == epic_1.key


@mock.patch('jira_offline.jira.api_post')
@mock.patch('jira_offline.jira.api_put')
def test_jira__update_issue__successful_put_results_in_get(mock_api_put, mock_api_post, mock_jira_core, project):
    '''
    Ensure a successful PUT of an Issue is followed by a GET
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # Don't try to fetch during this test
    mock_jira_core.fetch_issue = mock.Mock(return_value=issue_1)

    mock_jira_core.update_issue(
        project, IssueUpdate(merged_issue=issue_1, modified={'priority'})
    )

    mock_api_put.assert_called_with(
        project, f'/rest/api/2/issue/{issue_1.key}', data={'fields': {'priority': {'name': 'Normal'}}}
    )
    assert not mock_api_post.called
    mock_jira_core.fetch_issue.assert_called_with(project, issue_1.key)
    assert mock_jira_core.write_issues.called


@mock.patch('jira_offline.jira.api_post')
@mock.patch('jira_offline.jira.api_put')
def test_jira__update_issue__calls_transition_api_on_status_change(mock_api_put, mock_api_post, mock_jira_core, project):
    '''
    Ensure a successful POST to /transitions happens when Issue.status is modified
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    # Don't try to fetch during this test
    mock_jira_core.fetch_issue = mock.Mock(return_value=issue_1)

    mock_jira_core.update_issue(
        project, IssueUpdate(merged_issue=issue_1, modified={'status'})
    )

    mock_api_put.assert_called_with(
        project, f'/rest/api/2/issue/{issue_1.key}', data={'fields': {}}
    )
    mock_api_post.assert_called_with(
        project, f'/rest/api/2/issue/{issue_1.key}/transitions', data={'transition': {}}
    )
    mock_jira_core.fetch_issue.assert_called_with(project, issue_1.key)
    assert mock_jira_core.write_issues.called


@mock.patch('jira_offline.jira.api_put', side_effect=JiraApiError)
@mock.patch('jira_offline.jira.api_get')
def test_jira__update_issue__failed_put_raises_exception(
        mock_api_get, mock_api_put, mock_jira_core, project
    ):
    '''
    Ensure a failed PUT of an Issue causes an exception
    '''
    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1 = Issue.deserialize(ISSUE_1, project)
        issue_1.commit()

    # Don't write to disk during tests
    mock_jira_core.write_issues = mock.Mock()

    with pytest.raises(JiraApiError):
        mock_jira_core.update_issue(
            project, IssueUpdate(merged_issue=issue_1, modified={'priority'})
        )

    assert mock_api_put.called
    assert not mock_api_get.called
    assert not mock_jira_core.write_issues.called


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

    mock_api_get.assert_called_with(project, f'/rest/api/2/issue/{ISSUE_1["key"]}', params={'expand': 'transitions'})
    assert mock_jiraapi_object_to_issue.called


def test_jira__keys__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.keys() respects a filter set in jira.filter
    '''
    # Setup the project configuration with two projects
    project_1 = ProjectMeta('FIRST')
    project_2 = ProjectMeta('SECOND')
    mock_jira_core.config.projects = {project_1.id: project_1, project_2.id: project_2}

    issue_1 = Issue.deserialize(ISSUE_1, project=project_1)

    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project=project_2)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1.commit()
        issue_2.commit()

    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        assert list(mock_jira_core.keys()) == ['TEST-71', 'TEST-72']

        mock_jira_core.filter.set('project = SECOND')

        assert list(mock_jira_core.keys()) == ['TEST-72']


def test_jira__values__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.values() respects a filter set in jira.filter
    '''
    # Setup the project configuration with two projects
    project_1 = ProjectMeta('FIRST')
    project_2 = ProjectMeta('SECOND')
    mock_jira_core.config.projects = {project_1.id: project_1, project_2.id: project_2}

    issue_1 = Issue.deserialize(ISSUE_1, project=project_1)

    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project=project_2)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1.commit()
        issue_2.commit()

    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        assert list(mock_jira_core.values()) == [mock_jira_core['TEST-71'], mock_jira_core['TEST-72']]

        mock_jira_core.filter.set('project = SECOND')

        assert list(mock_jira_core.values()) == [mock_jira_core['TEST-72']]


def test_jira__items__respect_the_filter(mock_jira_core):
    '''
    Ensure that jira.items() respects a filter set in jira.filter
    '''
    # Setup the project configuration with two projects
    project_1 = ProjectMeta('FIRST')
    project_2 = ProjectMeta('SECOND')
    mock_jira_core.config.projects = {project_1.id: project_1, project_2.id: project_2}

    issue_1 = Issue.deserialize(ISSUE_1, project=project_1)

    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project=project_2)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira_core):
        issue_1.commit()
        issue_2.commit()

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
    assert len(mock_jira) == 0

    incoming_issue_1 = Issue.deserialize(ISSUE_1, project)

    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        incoming_issue_2 = Issue.deserialize(ISSUE_1, project)

    # Two issues passed from `sync.pull_single_project` into `jira.update`
    mock_jira.update([incoming_issue_1, incoming_issue_2])

    assert len(mock_jira) == 2

    compare_issue_helper(incoming_issue_1, mock_jira['TEST-71'])
    compare_issue_helper(incoming_issue_2, mock_jira['TEST-72'])


def test_jira__update__merge_new_issues_into_existing_dataframe(mock_jira, project):
    '''
    Ensure list of Issues can be appended without error when issues are already in the cache
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira):
        issue_1.commit()

    assert len(mock_jira) == 1

    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        incoming_issue_1 = Issue.deserialize(ISSUE_1, project)

    incoming_issue_2 = Issue.deserialize(EPIC_1, project)

    # Two issues passed from `sync.pull_single_project` into `jira.update`
    mock_jira.update([incoming_issue_1, incoming_issue_2])

    assert len(mock_jira) == 3

    compare_issue_helper(issue_1, mock_jira['TEST-71'])
    compare_issue_helper(incoming_issue_1, mock_jira['TEST-72'])
    compare_issue_helper(incoming_issue_2, mock_jira['TEST-1'])


def test_jira__update__merge_existing_issues_into_existing_dataframe(mock_jira, project):
    '''
    Ensure list of Issues can be updated in-place without error when the issues already in the cache
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira):
        issue_1.commit()
        issue_2.commit()

    assert len(mock_jira) == 2

    # Created fixtures with modified summary field coming from upstream
    with mock.patch.dict(ISSUE_1, {'summary': 'Updated summary 1'}):
        incoming_issue_1 = Issue.deserialize(ISSUE_1, project)
    with mock.patch.dict(ISSUE_1, {'summary': 'Updated summary 2', 'key': 'TEST-72'}):
        incoming_issue_2 = Issue.deserialize(ISSUE_1, project)

    # Two issues passed from `sync.pull_single_project` into `jira.update`
    mock_jira.update([incoming_issue_1, incoming_issue_2])

    assert len(mock_jira) == 2

    compare_issue_helper(incoming_issue_1, mock_jira['TEST-71'])
    compare_issue_helper(incoming_issue_2, mock_jira['TEST-72'])


def test_jira__modified_filter_none(mock_jira, project):
    '''
    Ensure jira.is_modified() enables filtering when no issues are modified
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira):
        issue_1.commit()
        issue_2.commit()

    with mock.patch('jira_offline.jira.jira', mock_jira):
        assert len(mock_jira._df[mock_jira.is_modified()]) == 0


def test_jira__modified_filter_some(mock_jira, project):
    '''
    Ensure jira.is_modified() enables filtering when some issues are modified
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue_2 = Issue.deserialize(ISSUE_1, project)

    # Make a modification to second issue
    issue_2.assignee = 'dave'

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira):
        issue_1.commit()
        issue_2.commit()

    with mock.patch('jira_offline.jira.jira', mock_jira):
        assert len(mock_jira._df[mock_jira.is_modified()]) == 1


def test_jira__new_filter(mock_jira, project):
    '''
    Ensure jira.is_new() enables filtering for new issues
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)
    issue_new = Issue.deserialize(ISSUE_NEW, project)

    # Setup the Jira DataFrame
    with mock.patch('jira_offline.jira.jira', mock_jira):
        issue_1.commit()
        issue_new.commit()

    with mock.patch('jira_offline.jira.jira', mock_jira):
        assert len(mock_jira._df[mock_jira.is_new()]) == 1

from unittest import mock

import pytest

from fixtures import EPIC_1, ISSUE_1
from helpers import compare_issue_helper
from jira_offline.create import (create_issue, import_issue, _import_new_issue,
                                 _import_modified_issue)
from jira_offline.exceptions import ImportFailed, InvalidIssueType
from jira_offline.models import Issue


def test_create__create_issue__loads_issues_when_cache_empty(mock_jira, project):
    '''
    Ensure create_issue() calls load_issues() when the cache is empty
    '''
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        create_issue(project, 'Story', 'This is a summary')

    assert mock_jira.load_issues.called


def test_create__create_issue__does_not_load_issues_when_cache_full(mock_jira, project):
    '''
    Ensure create_issue() NOT calls load_issues() when the cache is full
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        create_issue(project, 'Story', 'This is a summary')

    assert not mock_jira.load_issues.called


def test_create__create_issue__raises_on_invalid_issuetype(mock_jira, project):
    '''
    Ensure create_issue() raises an exception on an invalid issuetype
    '''
    with mock.patch('jira_offline.jira.jira', mock_jira):
        with pytest.raises(InvalidIssueType):
            create_issue(project, 'FakeType', 'This is a summary')


def test_create__create_issue__adds_issue_to_dataframe(mock_jira, project):
    '''
    Ensure create_issue() adds the new Issue to the DataFrame
    '''
    with mock.patch('jira_offline.jira.jira', mock_jira):
        offline_issue = create_issue(project, 'Story', 'This is a summary')

    assert mock_jira[offline_issue.key]


def test_create__create_issue__mandatory_fields_are_set_in_new_issue(mock_jira, project):
    '''
    Ensure create_issue() sets the mandatory fields passed as args (not kwargs)
    '''
    with mock.patch('jira_offline.jira.jira', mock_jira):
        offline_issue = create_issue(project, 'Story', 'This is a summary')

    assert offline_issue.project == project
    assert offline_issue.issuetype == 'Story'
    assert offline_issue.summary == 'This is a summary'
    assert offline_issue.description is None
    assert len(offline_issue.key) == 36  # UUID

    # Validate a roundtrip via the DataFrame
    assert mock_jira[offline_issue.key].project == project
    assert mock_jira[offline_issue.key].issuetype == 'Story'
    assert mock_jira[offline_issue.key].summary == 'This is a summary'
    assert mock_jira[offline_issue.key].description is None
    assert len(mock_jira[offline_issue.key].key) == 36  # UUID


def test_create__create_issue__kwargs_are_set_in_new_issue(mock_jira, project):
    '''
    Ensure create_issue() sets the extra fields passed as kwargs (not args)
    '''
    # Add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.edit.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        offline_issue = create_issue(project, 'Story', 'This is a summary', epic_link='TEST-1')

    assert offline_issue.epic_link == 'TEST-1'

    # Validate a roundtrip via the DataFrame
    assert mock_jira[offline_issue.key].epic_link == 'TEST-1'


def test_create__create_issue__kwargs_are_set_in_new_issue_extended(mock_jira, project):
    '''
    Ensure create_issue() sets the extra fields passed as kwargs (not args)
    '''
    # Setup an extended customfield on this project
    project.customfields.extended = {'arbitrary_key': 'customfield_10111'}

    # Add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.jira.jira', mock_jira):
        offline_issue = create_issue(project, 'Story', 'This is a summary', arbitrary_key='arbitrary_value')

    assert offline_issue.extended['arbitrary_key'] == 'arbitrary_value'

    # Validate a roundtrip via the DataFrame
    assert mock_jira[offline_issue.key].extended['arbitrary_key'] == 'arbitrary_value'


@pytest.mark.parametrize('epic_link_value', [
    ('This is an epic'),
    ('0.1: Epic about a thing'),
])
def test_create__create_issue__issue_is_mapped_to_existing_epic_summary(mock_jira, project, epic_link_value):
    '''
    Ensure create_issue() maps new Issue to the matching epic, when supplied epic_link matches the
    epic's summary OR epic_name
    '''
    # add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.edit.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        new_issue = create_issue(project, 'Story', 'This is summary', epic_link=epic_link_value)

    # assert new Issue to linked to the epic
    assert new_issue.epic_link == mock_jira['TEST-1'].key


@mock.patch('jira_offline.create._import_new_issue')
def test_create__import_issue__calls_import_new_when_obj_missing_key(mock_import_new, mock_jira):
    '''
    Ensure import_issue calls _import_new_issue
    '''
    with mock.patch('jira_offline.create.jira', mock_jira):
        _, is_new = import_issue({})

    assert mock_import_new.called
    assert is_new is True


@mock.patch('jira_offline.create._import_modified_issue')
def test_create__import_issue__calls_import_updated_when_obj_has_key(mock_import_modified, mock_jira):
    '''
    Ensure import_issue calls _import_updated
    '''
    with mock.patch('jira_offline.create.jira', mock_jira):
        _, is_new = import_issue({'key': 'EGG'})

    assert mock_import_modified.called
    assert is_new is False


@mock.patch('jira_offline.create.patch_issue_from_dict')
def test_create__import_modified_issue__returns_issue_if_mod_made(mock_patch_issue_from_dict, mock_jira, project):
    '''
    Ensure `_import_modified_issue` returns the Issue object if a modification is made.
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-71'] = issue = Issue.deserialize(ISSUE_1, project)

    mock_patch_issue_from_dict.return_value = True

    # import same test JSON twice
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        imported_issue = _import_modified_issue({'key': 'TEST-71', 'summary': 'This is the story summary'})

    compare_issue_helper(issue, imported_issue)


@mock.patch('jira_offline.create.patch_issue_from_dict')
def test_create__import_modified_issue__returns_none_if_no_mod_made(mock_patch_issue_from_dict, mock_jira, project):
    '''
    Ensure `_import_modified_issue` returns None if a modification is NOT made.
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    mock_patch_issue_from_dict.return_value = False

    # import same test JSON twice
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        imported_issue = _import_modified_issue({'key': 'TEST-71', 'summary': 'This is the story summary'})

    assert imported_issue is None


@mock.patch('jira_offline.create.find_project')
@mock.patch('jira_offline.create.create_issue')
def test_create__import_new_issue__calls_create_issue(mock_create_issue, mock_find_project, mock_jira, project):
    '''
    Ensure _import_new_issue() calls create_issue with the correct params
    '''
    mock_find_project.return_value = project

    import_dict = {
        'project': 'TEST',
        'issuetype': 'Epic',
        'summary': 'Egg',
        'story_points': 99,
        'description': 'bacon',
    }

    with mock.patch('jira_offline.create.jira', mock_jira):
        _import_new_issue(import_dict)

    mock_create_issue.assert_called_with(
        project, 'Epic', 'Egg', strict=False, story_points=99, description='bacon'
    )


@pytest.mark.parametrize('keys', [
    (('project', 'issuetype')),
    (('project', 'summary')),
    (('issuetype', 'summary')),
])
def test_create__import_new_issue__raises_on_key_missing(mock_jira, keys):
    '''
    Ensure _import_new_issue() raises when mandatory keys are missing
    '''
    with mock.patch('jira_offline.create.jira', mock_jira):
        with pytest.raises(ImportFailed):
            _import_new_issue({k[0]:1 for k in zip(keys)})

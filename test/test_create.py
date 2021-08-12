import copy
from unittest import mock

import pytest

from fixtures import EPIC_1, ISSUE_1
from jira_offline.exceptions import (EpicNotFound, EpicSearchStrUsedMoreThanOnce, ImportFailed,
                                     InvalidIssueType)
from jira_offline.create import (create_issue, find_epic_by_reference, import_issue, _import_new_issue,
                                 _import_modified_issue, patch_issue_from_dict)
from jira_offline.models import Issue


def test_create__create_issue__loads_issues_when_cache_empty(mock_jira, project):
    '''
    Ensure create_issue() calls load_issues() when the cache is empty
    '''
    with mock.patch('jira_offline.create.jira', mock_jira):
        create_issue(project, 'Story', 'This is a summary')

    assert mock_jira.load_issues.called


def test_create__create_issue__does_not_load_issues_when_cache_full(mock_jira, project):
    '''
    Ensure create_issue() NOT calls load_issues() when the cache is full
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-72'] = Issue.deserialize(ISSUE_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        create_issue(project, 'Story', 'This is a summary')

    assert not mock_jira.load_issues.called


def test_create__create_issue__raises_on_invalid_issuetype(mock_jira, project):
    '''
    Ensure create_issue() raises an exception on an invalid issuetype
    '''
    with mock.patch('jira_offline.create.jira', mock_jira):
        with pytest.raises(InvalidIssueType):
            create_issue(project, 'FakeType', 'This is a summary')


def test_create__create_issue__adds_issue_to_self_and_calls_write_issues(mock_jira, project):
    '''
    Ensure create_issue() adds the new Issue to self, and writes the issue cache
    '''
    with mock.patch('jira_offline.create.jira', mock_jira):
        offline_issue = create_issue(project, 'Story', 'This is a summary')

    assert mock_jira[offline_issue.key]
    assert mock_jira.write_issues.called


def test_create__create_issue__mandatory_fields_are_set_in_new_issue(mock_jira, project):
    '''
    Ensure create_issue() sets the mandatory fields passed as args (not kwargs)
    '''
    with mock.patch('jira_offline.create.jira', mock_jira):
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
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
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
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        offline_issue = create_issue(project, 'Story', 'This is a summary', arbitrary_key='arbitrary_value')

    assert offline_issue.extended['arbitrary_key'] == 'arbitrary_value'

    # Validate a roundtrip via the DataFrame
    assert mock_jira[offline_issue.key].extended['arbitrary_key'] == 'arbitrary_value'


def test_create__create_issue__raises_exception_when_passed_an_unknown_epic_link(mock_jira, project):
    '''
    Ensure create_issue() raises exception when an epic_link is passed which does not match an
    existing epic on either summary OR epic_name
    '''
    # add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        with pytest.raises(EpicNotFound):
            create_issue(project, 'Story', 'This is summary', epic_link='Nothing')


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
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    with mock.patch('jira_offline.create.jira', mock_jira), mock.patch('jira_offline.jira.jira', mock_jira):
        new_issue = create_issue(project, 'Story', 'This is summary', epic_link=epic_link_value)

    # assert new Issue to linked to the epic
    assert new_issue.epic_link == mock_jira['TEST-1'].key


def test_create__find_epic_by_reference__match_by_key(mock_jira):
    '''
    Ensure find_epic_by_reference() returns an Issue of epic type when passed the Issue key
    '''
    # add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        epic = find_epic_by_reference('TEST-1')

    assert epic == mock_jira['TEST-1']


def test_create__find_epic_by_reference__match_by_summary(mock_jira):
    '''
    Ensure find_epic_by_reference() returns an Issue of epic type when passed a summary
    '''
    # add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    with mock.patch('jira_offline.create.jira', mock_jira), mock.patch('jira_offline.jira.jira', mock_jira):
        epic = find_epic_by_reference('This is an epic')

    assert epic == mock_jira['TEST-1']


def test_create__find_epic_by_reference__match_by_epic_name(mock_jira):
    '''
    Ensure find_epic_by_reference() returns an Issue of epic type when passed an epic_name
    '''
    # add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1)

    with mock.patch('jira_offline.create.jira', mock_jira), mock.patch('jira_offline.jira.jira', mock_jira):
        epic = find_epic_by_reference('0.1: Epic about a thing')

    assert epic == mock_jira['TEST-1']


def test_create__find_epic_by_reference__raise_on_failed_to_match(mock_jira):
    '''
    Ensure exception raised when epic not found
    '''
    with mock.patch('jira_offline.create.jira', mock_jira), mock.patch('jira_offline.jira.jira', mock_jira):
        with pytest.raises(EpicNotFound):
            find_epic_by_reference('fake epic reference')


def test_create__find_epic_by_reference__raise_on_duplicate_ref_string(mock_jira):
    '''
    Ensure exception raised when there are two epics matching the search string
    '''
    # add two Epic fixtures to the Jira dict
    mock_jira['EPIC-1'] = Issue.deserialize(EPIC_1)
    epic2 = copy.deepcopy(Issue.deserialize(EPIC_1))
    epic2.key = 'EPIC-2'
    mock_jira['EPIC-2'] = epic2

    with mock.patch('jira_offline.create.jira', mock_jira), mock.patch('jira_offline.jira.jira', mock_jira):
        with pytest.raises(EpicSearchStrUsedMoreThanOnce):
            find_epic_by_reference('This is an epic')


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


def test_create__import_modified_issue__merges_writable_fields(mock_jira):
    '''
    Ensure _import_modified_issue() merges imported data onto writable fields

    This test notably doesn't mock the function merge_issues(); failures in this test will uncover
    problems in functions down the callstack
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    # import some modified fields for Issue key=issue1
    import_dict = {
        'key': 'TEST-71',
        'story_points': 99,
        'description': 'bacon',
    }

    with mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira):
        imported_issue = _import_modified_issue(import_dict)

    assert isinstance(imported_issue, Issue)
    assert imported_issue.key == 'TEST-71'
    assert imported_issue.story_points == 99
    assert imported_issue.description == 'bacon'


def test_create__import_modified_issue__doesnt_merge_readonly_fields(mock_jira):
    '''
    Ensure _import_modified_issue() doesnt merge imported data onto readonly fields

    This test notably doesn't mock the function merge_issues(); failures in this test will uncover
    problems in functions down the callstack
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    # import a readonly field against TEST-71
    import_dict = {'key': 'TEST-71', 'project_id': 'hoganp'}

    with mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira):
        imported_issue = _import_modified_issue(import_dict)

    assert imported_issue.project_id == '99fd9182cfc4c701a8a662f6293f4136201791b4'


def test_create__import_modified_issue__produces_issue_with_diff(mock_jira):
    '''
    Ensure _import_modified_issue() produces an Issue with a diff

    This test notably doesn't mock the function merge_issues(); failures in this test will uncover
    problems in functions down the callstack
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    import_dict = {'key': 'TEST-71', 'assignee': 'hoganp'}

    with mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira):
        imported_issue = _import_modified_issue(import_dict)

    assert imported_issue.assignee == 'hoganp'
    assert imported_issue.diff() == [('change', 'assignee', ('hoganp', 'danil1'))]


def test_create__import_modified_issue__idempotent(mock_jira):
    '''
    Ensure an issue can be imported twice without breaking the diff behaviour

    This test notably doesn't mock the function merge_issues(); failures in this test will uncover
    problems in functions down the callstack
    '''
    # add an Issue fixture to the Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    import_dict = {'key': 'TEST-71', 'assignee': 'hoganp'}

    # import same test JSON twice
    with mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira):
        imported_issue = _import_modified_issue(import_dict)

    assert imported_issue.assignee == 'hoganp'
    assert imported_issue.diff() == [('change', 'assignee', ('hoganp', 'danil1'))]

    with mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira):
        imported_issue = _import_modified_issue(import_dict)

    assert imported_issue.assignee == 'hoganp'
    assert imported_issue.diff() == [('change', 'assignee', ('hoganp', 'danil1'))]


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

    mock_create_issue.assert_called_with(project, 'Epic', 'Egg', story_points=99, description='bacon')


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


def test_create__patch_issue_from_dict__set_string_to_value(mock_jira):
    '''
    Ensure an Issue can have attributes set a string
    '''
    issue = Issue.deserialize(ISSUE_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        patch_issue_from_dict(issue, {'assignee': 'eggs'})

    assert issue.assignee == 'eggs'


def test_create__patch_issue_from_dict__set_string_to_blank(mock_jira):
    '''
    Ensure an Issue can have attributes set
    '''
    issue = Issue.deserialize(ISSUE_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        patch_issue_from_dict(issue, {'assignee': ''})

    assert issue.assignee is None


def test_create__patch_issue_from_dict__set_priority(mock_jira):
    '''
    Ensure an Issue.priority can be set
    '''
    issue = Issue.deserialize(ISSUE_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        patch_issue_from_dict(issue, {'priority': 'Bacon'})

    assert issue.priority == 'Bacon'


def test_create__patch_issue_from_dict__set_extended_customfield(mock_jira):
    '''
    Ensure user-defined customfield "arbitrary-user-defined-field" can be set
    '''
    issue = Issue.deserialize(ISSUE_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        patch_issue_from_dict(issue, {'arbitrary-user-defined-field': 'eggs'})

    assert issue.extended['arbitrary-user-defined-field'] == 'eggs'


def test_create__patch_issue_from_dict__set_extended_customfield_extended(mock_jira):
    '''
    Ensure user-defined customfield "extended.arbitrary-user-defined-field" can be set, using the
    extended prefix
    '''
    issue = Issue.deserialize(ISSUE_1)

    with mock.patch('jira_offline.create.jira', mock_jira):
        patch_issue_from_dict(issue, {'extended.arbitrary-user-defined-field': 'eggs'})

    assert issue.extended['arbitrary-user-defined-field'] == 'eggs'

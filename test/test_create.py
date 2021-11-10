from unittest import mock

import pytest

from fixtures import EPIC_1, ISSUE_1
from helpers import compare_issue_helper
from jira_offline.exceptions import (EpicNotFound, EpicSearchStrUsedMoreThanOnce, ImportFailed,
                                     InvalidIssueType)
from jira_offline.create import (create_issue, find_linked_issue_by_ref, import_issue, _import_new_issue,
                                 _import_modified_issue, patch_issue_from_dict)
from jira_offline.models import CustomFields, Issue, ProjectMeta, Sprint


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

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        create_issue(project, 'Story', 'This is a summary')

    assert not mock_jira.load_issues.called


def test_create__create_issue__raises_on_invalid_issuetype(mock_jira, project):
    '''
    Ensure create_issue() raises an exception on an invalid issuetype
    '''
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        with pytest.raises(InvalidIssueType):
            create_issue(project, 'FakeType', 'This is a summary')


def test_create__create_issue__adds_issue_to_dataframe(mock_jira, project):
    '''
    Ensure create_issue() adds the new Issue to the DataFrame
    '''
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        offline_issue = create_issue(project, 'Story', 'This is a summary')

    assert mock_jira[offline_issue.key]


def test_create__create_issue__mandatory_fields_are_set_in_new_issue(mock_jira, project):
    '''
    Ensure create_issue() sets the mandatory fields passed as args (not kwargs)
    '''
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
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

    with mock.patch('jira_offline.create.jira', mock_jira), \
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

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
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

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        new_issue = create_issue(project, 'Story', 'This is summary', epic_link=epic_link_value)

    # assert new Issue to linked to the epic
    assert new_issue.epic_link == mock_jira['TEST-1'].key


def test_create__find_linked_issue_by_ref__match_by_key(mock_jira, project):
    '''
    Ensure `find_linked_issue_by_ref` returns an Issue of epic type when passed the Issue key
    '''
    # Add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = issue = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        linked_issue = find_linked_issue_by_ref('TEST-1')

    compare_issue_helper(issue, linked_issue)


@pytest.mark.parametrize('search_str', [
    ('This is an epic'),
    ('is an epic'),
])
def test_create__find_linked_issue_by_ref__match_by_summary(mock_jira, project, search_str):
    '''
    Ensure `find_linked_issue_by_ref` returns an Issue of epic type when passed a summary
    '''
    # Add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = issue = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        linked_issue = find_linked_issue_by_ref(search_str)

    compare_issue_helper(issue, linked_issue)


def test_create__find_linked_issue_by_ref__match_by_epic_name(mock_jira, project):
    '''
    Ensure `find_linked_issue_by_ref` returns an Issue of epic type when passed an epic_name
    '''
    # Add an Epic fixture to the Jira dict
    mock_jira['TEST-1'] = issue = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        linked_issue = find_linked_issue_by_ref('0.1: Epic about a thing')

    compare_issue_helper(issue, linked_issue)


def test_create__find_linked_issue_by_ref__raise_on_failed_to_match(mock_jira, project):
    '''
    Ensure exception raised when epic not found
    '''
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        with pytest.raises(EpicNotFound):
            find_linked_issue_by_ref('fake epic reference')


def test_create__find_linked_issue_by_ref__raise_on_duplicate_ref_string(mock_jira, project):
    '''
    Ensure exception raised when there are two epics matching the search string
    '''
    # Setup two epic fixtures
    mock_jira['TEST-1'] = Issue.deserialize(EPIC_1, project)

    with mock.patch.dict(EPIC_1, {'key': 'TEST-2'}):
        mock_jira['TEST-2'] = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        with pytest.raises(EpicSearchStrUsedMoreThanOnce):
            find_linked_issue_by_ref('This is an epic')


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
    with mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira):
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
    with mock.patch('jira_offline.jira.jira', mock_jira), \
            mock.patch('jira_offline.create.jira', mock_jira):
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


def test_create__patch_issue_from_dict__set_string_to_value(mock_jira, project):
    '''
    Ensure an Issue can have attributes set to a string
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'assignee': 'eggs'})

    assert issue.assignee == 'eggs'
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__set_string_to_blank(mock_jira, project):
    '''
    Ensure an Issue can have attributes set to an empty string and it will result in None
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'assignee': ''})

    assert issue.assignee is None
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__set_priority(mock_jira, project):
    '''
    Ensure an Issue.priority can be set
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'priority': 'Bacon'})

    assert issue.priority == 'Bacon'
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__skips_readonly_fields(mock_jira, project):
    '''
    Ensure readonly fields are skipped during a patch
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    assert issue.summary == 'This is the story summary'
    assert issue.project_id == '99fd9182cfc4c701a8a662f6293f4136201791b4'

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'key': 'TEST-71', 'project_id': 'Bacon', 'summary': 'Egg'})

    # Assert writeable field is modified, but the readonly value is not modified
    assert issue.summary == 'Egg'
    assert issue.project_id == '99fd9182cfc4c701a8a662f6293f4136201791b4'
    assert issue.commit.called
    assert patched is True


@pytest.mark.parametrize('param', [
    ('bacon'),
    ('egg,bacon'),
])
def test_create__patch_issue_from_dict__set_set(mock_jira, project, param):
    '''
    When patching a set, if a set is passed overwrite existing value, if a str is passed append to
    the existing set
    '''
    with mock.patch.dict(ISSUE_1, {'labels': set(['egg'])}):
        issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    assert issue.labels == {'egg'}

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'labels': param})

    assert issue.labels == {'egg', 'bacon'}
    assert issue.commit.called
    assert patched is True


@pytest.mark.skip(reason='Will succeed when there is a list-type field on Issue class')
@pytest.mark.parametrize('param', [
    ('bacon'),
    ('egg,bacon'),
])
def test_create__patch_issue_from_dict__set_list(mock_jira, project, param):
    '''
    When patching a list, if a list is passed, overwrite existing value, if a str is passed append to
    the existing list
    '''
    with mock.patch.dict(ISSUE_1, {'labels': ['egg']}):
        issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    assert issue.labels == ['egg']

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'labels': param})

    assert issue.labels == ['egg', 'bacon']
    assert issue.commit.called
    assert patched is True


@pytest.mark.parametrize('customfield_name', [
    ('arbitrary-user-defined-field'),
    ('extended.arbitrary-user-defined-field'),
])
def test_create__patch_issue_from_dict__set_extended_customfield(mock_jira, customfield_name):
    '''
    Ensure user-defined customfield "arbitrary-user-defined-field" can be set
    '''
    customfields = CustomFields(
        extended={'arbitrary-user-defined-field': 'customfield_10111'}
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {customfield_name: 'eggs'})

    assert issue.extended['arbitrary-user-defined-field'] == 'eggs'
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__ignore_undefined_customfield(mock_jira):
    '''
    Ensure arbitrary k:v mappings passed into `patch_issue_from_dict` are only applied as extended
    customfields if they are user-defined in config.
    '''
    customfields = CustomFields(
        extended={}
    )
    project = ProjectMeta(key='TEST', customfields=customfields)

    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'arbitrary-user-defined-field': 'eggs'})

    assert issue.extended == {}
    assert not issue.commit.called
    assert patched is False


def test_create__patch_issue_from_dict__uses_reset_before_edit(mock_jira):
    '''
    Ensure that the reset_before_edit metadata field causes a single-field reset before a patch
    '''
    project = ProjectMeta(
        key='TEST',
        customfields=CustomFields(sprint='customfield_10300'),
        sprints={
            1: Sprint(id=1, name='Sprint 1', active=True),
            2: Sprint(id=2, name='Sprint 2', active=False),
            3: Sprint(id=3, name='Sprint 3', active=False),
        },
    )

    # Create an issue which already exists in a sprint
    with mock.patch.dict(ISSUE_1, {'sprint': [{'id': 1, 'name': 'Sprint 1', 'active': True}]}):
        issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    # Add the issue to another sprint
    issue.sprint.add(Sprint(id=2, name='Sprint 2', active=False))

    assert issue.sprint == {
        Sprint(id=1, name='Sprint 1', active=True),
        Sprint(id=2, name='Sprint 2', active=False),
    }

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'sprint': 'Sprint 3'})

    # Ensure the modification of sprint before the patch is reset, leaving just sprint 1 & 3 on the issue
    assert issue.sprint == {
        Sprint(id=1, name='Sprint 1', active=True),
        Sprint(id=3, name='Sprint 3', active=False),
    }
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__epic_name_ignored_on_story_issuetype(mock_jira, project):
    '''
    Ensure the field Issue.epic_name is only imported which issuetype==Epic
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'epic_name': 'eggs'})

    assert issue.epic_name is None
    assert not issue.commit.called
    assert patched is False


def test_create__patch_issue_from_dict__epic_name_patched_on_epic_issuetype(mock_jira, project):
    '''
    Ensure the field Issue.epic_name is only imported which issuetype==Epic
    '''
    issue = Issue.deserialize(EPIC_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'epic_name': 'eggs'})

    assert issue.epic_name == 'eggs'
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__ignores_unused_customfields(mock_jira):
    '''
    Ensure the customfields on the Issue object are not set when the customfield IS NOT configured
    for the project
    '''
    project = ProjectMeta(
        key='TEST',
        customfields=CustomFields(epic_name='customfield_10100')
    )
    with mock.patch.dict(EPIC_1, {'epic_name': None}):
        issue = Issue.deserialize(EPIC_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'epic_name': 'eggs'})

    assert issue.epic_name == 'eggs'
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__doesnt_ignore_not_unused_customfields(mock_jira):
    '''
    Ensure the customfields on the Issue object are set when the customfield IS configured for the
    project
    '''
    project = ProjectMeta(
        key='TEST',
        customfields=CustomFields()
    )
    with mock.patch.dict(EPIC_1, {'epic_name': None}):
        issue = Issue.deserialize(EPIC_1, project)

    issue.commit = mock.Mock()

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'epic_name': 'eggs'})

    assert issue.epic_name is None
    assert not issue.commit.called
    assert patched is False


@pytest.mark.parametrize('field', [
    ('epic_link'),
    ('parent_link'),
])
@mock.patch('jira_offline.create.find_linked_issue_by_ref')
def test_create__patch_issue_from_dict__links_issue(mock_find_linked_issue_by_ref, mock_jira, field):
    '''
    Ensure the fields Issue.epic_link and Issue.parent_link are set correctly
    '''
    project = ProjectMeta(
        'TEST',
        customfields=CustomFields(
            epic_link='customfield_10100',
            parent_link='customfield_10100'
        ),
    )
    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    mock_find_linked_issue_by_ref.return_value = linked = Issue.deserialize(EPIC_1, project)

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {field: 'eggs'})

    mock_find_linked_issue_by_ref.assert_called_with('eggs')
    assert getattr(issue, field) == linked.key
    assert issue.commit.called
    assert patched is True


def test_create__patch_issue_from_dict__idempotent(mock_jira, project):
    '''
    Ensure an issue can be patched twice and produces an identical diff
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    issue.commit = mock.Mock()

    # import same test JSON twice
    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'key': 'TEST-71', 'assignee': 'hoganp'})

    assert issue.assignee == 'hoganp'
    assert issue.diff() == [('change', 'assignee', ('hoganp', 'danil1'))]
    assert issue.commit.called
    assert patched is True

    with mock.patch('jira_offline.create.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        patched = patch_issue_from_dict(issue, {'key': 'TEST-71', 'assignee': 'hoganp'})

    assert issue.assignee == 'hoganp'
    assert issue.diff() == [('change', 'assignee', ('hoganp', 'danil1'))]
    assert issue.commit.called
    assert patched is True

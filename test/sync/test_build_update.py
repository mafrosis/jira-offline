import datetime
from unittest import mock

import pytest

from fixtures import ISSUE_1, ISSUE_NEW
from helpers import modified_issue_helper
from jira_offline.models import Issue
from jira_offline.sync import Conflict, build_update


def test_build_update__ignores_readonly_fields(project):
    '''
    Modified readonly fields must be ignored during build_update
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    # Create a modified issue where only a readonly field is modified
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), updated=datetime.datetime.now())

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'
    assert update_obj.merged_issue.updated == base_issue.updated


def test_build_update__base_unmodified_and_updated_modified(project):
    '''
    Ensure NO conflict when:
      - base NOT changed
      - updated changed to field B=1
    '''
    # Create an unmodified base issue fixture
    base_issue = Issue.deserialize(ISSUE_1, project)

    # Create a modified upstream issue fixture
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_and_updated_unmodified(project):
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated NOT changed
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    # Create an unmodified upstream issue fixture
    updated_issue = Issue.deserialize(ISSUE_1, project)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_and_updated_modified_on_conflicting_str(project):
    '''
    Ensure conflict when (for str type):
      - base changed to field A="1"
      - updated changed to field A="2"
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    # Create a conflicting modified issue fixture
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='murphye')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert update_obj.conflicts == {
        'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}
    }
    assert isinstance(update_obj.merged_issue.assignee, Conflict)


def test_build_update__base_modified_and_updated_modified_on_conflicting_str_extended(project):
    '''
    Ensure conflict when (for str type):
      - base changed to field A="1"
      - updated changed to field A="2"

    Special-case test for extended customfields (which are always string type)
    '''
    # Create a base issue fixture with a extended customfield
    with mock.patch.dict(ISSUE_1, {'extended': {'arbitrary_key': 'arbitrary_original'}}):
        base_issue = Issue.deserialize(ISSUE_1, project)

    # Modify the extended field
    base_issue.extended['arbitrary_key'] = 'arbitrary_base'

    # Create a conflicting modified issue fixture
    with mock.patch.dict(ISSUE_1, {'extended': {'arbitrary_key': 'arbitrary_updated'}}):
        updated_issue = Issue.deserialize(ISSUE_1, project)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'extended.arbitrary_key'}
    assert update_obj.conflicts == {
        'extended.arbitrary_key': {
            'original': 'arbitrary_original', 'updated': 'arbitrary_updated', 'base': 'arbitrary_base'
        }
    }
    assert isinstance(update_obj.merged_issue.extended['arbitrary_key'], Conflict)


def test_build_update__base_modified_and_updated_modified_on_conflicting_set(project):
    '''
    Ensure conflict when (for set type):
      - base changed to field A={1,2}
      - updated changed to field A={1,3}
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), fix_versions={'0.1', '0.2'})

    # Create a conflicting modified issue fixture
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), fix_versions={'0.1', '0.3'})

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'fix_versions'}
    assert update_obj.conflicts == {
        'fix_versions': {'original': ['0.1'], 'updated': ['0.1', '0.3'], 'base': ['0.1', '0.2']}
    }
    assert isinstance(update_obj.merged_issue.fix_versions, Conflict)


def test_build_update__base_nonconflict_changes_returned_in_merged_issue(project):
    '''
    Ensure base changes returned in merged output, along with a conflict when:
      - base changed to field A=1 and B=1
      - updated changed to field A=2
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(
        Issue.deserialize(ISSUE_1, project), summary='This is modified', assignee='hoganp'
    )

    # Create a conflicting modified issue fixture, which conflicts on a different field
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='murphye')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert update_obj.conflicts == {
        'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}
    }
    assert isinstance(update_obj.merged_issue.assignee, Conflict)
    assert update_obj.merged_issue.summary == 'This is modified'


def test_build_update__updated_nonconflict_changes_returned_in_merged_issue(project):
    '''
    Ensure updated changes returned in merged output, along with a conflict when:
      - base changed to field A=2
      - updated changed to field A=1 and B=1
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='murphye')

    # Create a conflicting modified issue fixture, which conflicts on a different field
    updated_issue = modified_issue_helper(
        Issue.deserialize(ISSUE_1, project), summary='This is modified', assignee='hoganp'
    )

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert update_obj.conflicts == {
        'assignee': {'original': 'danil1', 'updated': 'hoganp', 'base': 'murphye'}
    }
    assert isinstance(update_obj.merged_issue.assignee, Conflict)
    assert update_obj.merged_issue.summary == 'This is modified'


def test_build_update__base_modified_and_updated_modified_on_different_fields(project):
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated changed to field B=1
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), fix_versions={'0.1', '0.2'})

    # Create a modified issue fixture, modifying a different field
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == {'0.1', '0.2'}
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_and_updated_modified_on_same_fields_with_same_value(project):
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated changed to field A=1
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    # Create a modified issue fixture, with precisely same change as the base_issue
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_on_multiple_fields_and_updated_modified_on_single_with_same_values(project):
    '''
    Ensure NO conflict when:
      - base changed to field A=1 and B=2
      - updated changed to field A=1
    '''
    # Create a modified base issue fixture (modified on two fields)
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp', summary='This is modified')

    # Create a modified issue fixture, with same change on assignee as the base_issue
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.summary == 'This is modified'
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_on_single_field_and_updated_modified_on_multiple_with_same_values(project):
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated changed to field A=1 and B=2
    '''
    # Create a modified base issue fixture (modified on two fields)
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    # Create a modified issue fixture, with same change on assignee as the base_issue
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp', summary='This is modified')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.summary == 'This is modified'
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__new_issue(project):
    '''
    Validate build_update with NEW issue
    '''
    # Create a new issue fixture
    new_issue = Issue.deserialize(ISSUE_NEW, project)

    # for new Issues created offline, the updated_issue is None
    update_obj = build_update(new_issue, None)

    # modified fields should match all non-readonly fields, which are set in ISSUE_NEW fixture
    assert update_obj.modified == {
        'project_id', 'key', 'description', 'epic_link', 'fix_versions', 'issuetype', 'reporter', 'summary',
    }
    assert not update_obj.conflicts

    assert new_issue.project_id == update_obj.merged_issue.project_id
    assert new_issue.key == update_obj.merged_issue.key
    assert new_issue.description == update_obj.merged_issue.description
    assert new_issue.epic_link == update_obj.merged_issue.epic_link
    assert new_issue.fix_versions == update_obj.merged_issue.fix_versions
    assert new_issue.issuetype == update_obj.merged_issue.issuetype
    assert new_issue.reporter == update_obj.merged_issue.reporter
    assert new_issue.summary == update_obj.merged_issue.summary


def test_build_update__new_issue_with_extended_customfield(project):
    '''
    Validate build_update with NEW issue that has extended customfields
    '''
    # Create a new issue fixture
    with mock.patch.dict(ISSUE_NEW, {'extended': {'arbitrary_key': 'arbitrary_original'}}):
        new_issue = Issue.deserialize(ISSUE_NEW, project)
        new_issue.fix_versions = set()
        new_issue.epic_link = None

    # for new Issues created offline, the updated_issue is None
    update_obj = build_update(new_issue, None)

    # modified fields should match all non-readonly fields
    assert update_obj.modified == {
        'project_id', 'key', 'description', 'issuetype', 'reporter', 'summary', 'extended.arbitrary_key',
    }
    assert not update_obj.conflicts

    assert new_issue.project_id == update_obj.merged_issue.project_id
    assert new_issue.key == update_obj.merged_issue.key
    assert new_issue.description == update_obj.merged_issue.description
    assert new_issue.epic_link == update_obj.merged_issue.epic_link
    assert new_issue.fix_versions == update_obj.merged_issue.fix_versions
    assert new_issue.issuetype == update_obj.merged_issue.issuetype
    assert new_issue.reporter == update_obj.merged_issue.reporter
    assert new_issue.summary == update_obj.merged_issue.summary


@pytest.mark.parametrize('val', [
    '',
    None,
])
def test_build_update__base_unmodified_and_updated_modified_to_empty_string(project, val):
    '''
    Ensure an unmodified Issue can have a field set to empty string
    '''
    # Create a unmodified base issue fixture
    base_issue = Issue.deserialize(ISSUE_1, project)

    # Create a modified issue fixture, with an empty assignee
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee=val)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee is None


@pytest.mark.parametrize('val', [
    '',
    None,
])
def test_build_update__base_modified_and_updated_modified_to_empty_string(project, val):
    '''
    Ensure a modified Issue can have a field set to empty string
    '''
    # Create a modified base issue fixture
    base_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), fix_versions={'0.1', '0.2'})

    # Create a modified issue fixture, with an empty assignee
    updated_issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee=val)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == {'0.1', '0.2'}
    assert update_obj.merged_issue.assignee is None


@pytest.mark.parametrize('value_to_append', ['0', '2'])
def test_build_update__base_unmodified_and_updated_modified_to_append_to_set(project, value_to_append):
    '''
    Ensure an unmodified Issue can have a set field appended when it already has a value.

    This test ensures correct behaviour when the _ordering_ of a set changes during an append.

    The sets here use integers, as it's the simplest way to ensure a deterministic (and thus testable)
    order on the resulting set (https://stackoverflow.com/a/51949325/425050)
    '''
    # Create test fixtures with starting Issue.fix_version == set(1)
    with mock.patch.dict(ISSUE_1, {'fix_versions': {'1'}}):
        base_issue = Issue.deserialize(ISSUE_1, project)
        updated_issue = Issue.deserialize(ISSUE_1, project)

    # Modify the upstream fixture
    updated_issue.fix_versions.add(value_to_append)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == {'1', value_to_append}


@pytest.mark.parametrize('value_to_append', ['0', '2'])
def test_build_update__base_modified_and_updated_modified_to_append_to_set(project, value_to_append):
    '''
    Ensure an unmodified Issue can have a set field appended when it already has a value.

    This test ensures correct behaviour when the _ordering_ of a set changes during an append.

    The sets here use integers, as it's the simplest way to ensure a deterministic (and thus testable)
    order on the resulting set (https://stackoverflow.com/a/51949325/425050)
    '''
    # Create test fixtures with starting Issue.fix_version == set(1)
    with mock.patch.dict(ISSUE_1, {'fix_versions': {'1'}}):
        base_issue = Issue.deserialize(ISSUE_1, project)
        updated_issue = Issue.deserialize(ISSUE_1, project)

    # Modify the upstream fixture
    updated_issue.fix_versions.add(value_to_append)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == {'1', value_to_append}

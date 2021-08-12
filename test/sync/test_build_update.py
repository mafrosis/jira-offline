import copy

import pytest

from fixtures import (ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF,
                      ISSUE_1_WITH_UPDATED_DIFF, ISSUE_NEW)
from jira_offline.models import Issue
from jira_offline.sync import Conflict, build_update


def test_build_update__ignores_readonly_fields():
    '''
    Modified readonly fields must be ignored during build_update
    '''
    # create unmodified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # create modified issue as upstream (readonly field is only one modified)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_UPDATED_DIFF)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'
    assert update_obj.merged_issue.updated == base_issue.updated


def test_build_update__base_unmodified_and_updated_modified():
    '''
    Ensure NO conflict when:
      - base NOT changed
      - updated changed to field B=1
    '''
    # create unmodified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1)
    # supply a modified Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_and_updated_unmodified():
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated NOT changed
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # supply an unmodified Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_and_updated_modified_on_conflicting_str():
    '''
    Ensure conflict when (for str type):
      - base changed to field A="1"
      - updated changed to field A="2"
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # supply a conflicting modified Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.assignee = 'murphye'

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert update_obj.conflicts == {
        'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}
    }
    assert isinstance(update_obj.merged_issue.assignee, Conflict)


def test_build_update__base_modified_and_updated_modified_on_conflicting_str_extended():
    '''
    Ensure conflict when (for str type):
      - base changed to field A="1"
      - updated changed to field A="2"

    Special-case test for extended customfields (which are always string type)
    '''
    # Create a base Issue fixture with a extended customfield
    issue_fixture = copy.copy(ISSUE_1)
    issue_fixture['extended'] = {'arbitrary_key': 'arbitrary_original'}
    base_issue = Issue.deserialize(issue_fixture)

    # Modify the extended field
    base_issue.extended['arbitrary_key'] = 'arbitrary_base'

    # Supply a conflicting Issue
    issue_fixture['extended'] = {'arbitrary_key': 'arbitrary_updated'}
    updated_issue = Issue.deserialize(issue_fixture)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'extended.arbitrary_key'}
    assert update_obj.conflicts == {
        'extended.arbitrary_key': {
            'original': 'arbitrary_original', 'updated': 'arbitrary_updated', 'base': 'arbitrary_base'
        }
    }
    assert isinstance(update_obj.merged_issue.extended['arbitrary_key'], Conflict)


def test_build_update__base_modified_and_updated_modified_on_conflicting_set():
    '''
    Ensure conflict when (for set type):
      - base changed to field A={1,2}
      - updated changed to field A={1,3}
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)
    # supply a conflicting modified Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.fix_versions.add('0.3')

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'fix_versions'}
    assert update_obj.conflicts == {
        'fix_versions': {'original': ['0.1'], 'updated': ['0.1', '0.3'], 'base': ['0.1', '0.2']}
    }
    assert isinstance(update_obj.merged_issue.fix_versions, Conflict)


def test_build_update__base_nonconflict_changes_returned_in_merged_issue():
    '''
    Ensure base changes returned in merged output, along with a conflict when:
      - base changed to field A=1 and B=1
      - updated changed to field A=2
    '''
    # create a modified base Issue fixture, with an additional modified field
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    base_issue.summary = 'This is a test'
    # supply a conflicting modified Issue fixture (conflicting on a different field)
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.assignee = 'murphye'

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert update_obj.conflicts == {
        'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}
    }
    assert isinstance(update_obj.merged_issue.assignee, Conflict)
    assert update_obj.merged_issue.summary == 'This is a test'


def test_build_update__updated_nonconflict_changes_returned_in_merged_issue():
    '''
    Ensure updated changes returned in merged output, along with a conflict when:
      - base changed to field A=2
      - updated changed to field A=1 and B=1
    '''
    # create a modified base Issue fixture, with an additional modified field
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    updated_issue.summary = 'This is a test'
    # make a conflicting change on the updated issue
    base_issue = Issue.deserialize(ISSUE_1)
    base_issue.assignee = 'murphye'

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert update_obj.conflicts == {
        'assignee': {'original': 'danil1', 'updated': 'hoganp', 'base': 'murphye'}
    }
    assert isinstance(update_obj.merged_issue.assignee, Conflict)
    assert update_obj.merged_issue.summary == 'This is a test'


def test_build_update__base_modified_and_updated_modified_on_different_fields():
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated changed to field B=1
    '''
    # create modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)
    # supply a modified Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == {'0.1', '0.2'}
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_and_updated_modified_on_same_fields_with_same_value():
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated changed to field A=1
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # supply a modified Issue fixture, with a matching modification to base
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_on_multiple_fields_and_updated_modified_on_single_with_same_values():
    '''
    Ensure NO conflict when:
      - base changed to field A=1 and B=2
      - updated changed to field A=1
    '''
    # create a modified base Issue fixture (modified on two fields)
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    base_issue.summary = 'This is a test'
    # supply a modified Issue fixture, with a matching modification to base
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.summary == 'This is a test'
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_on_single_field_and_updated_modified_on_multiple_with_same_values():
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated changed to field A=1 and B=2
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # supply a modified Issue fixture, with a matching modification to base, plus another change
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    updated_issue.summary = 'This is a test'

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.summary == 'This is a test'
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__new_issue():
    '''
    Validate build_update with NEW issue
    '''
    # create a new Issue fixture
    new_issue = Issue.deserialize(ISSUE_NEW)

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


def test_build_update__new_issue_with_extended_customfield():
    '''
    Validate build_update with NEW issue that has extended customfields
    '''
    # create a new Issue fixture
    issue_fixture = copy.copy(ISSUE_NEW)
    issue_fixture['extended'] = {'arbitrary_key': 'arbitrary_original'}
    del issue_fixture['fix_versions']
    del issue_fixture['epic_link']
    new_issue = Issue.deserialize(issue_fixture)

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
def test_build_update__base_unmodified_and_updated_modified_to_empty_string(val):
    '''
    Ensure an unmodified Issue can have a field set to empty string
    '''
    # create unmodified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1)
    # supply a modified Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.assignee = val

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee is None


def test_build_update__base_modified_and_updated_modified_to_empty_string():
    '''
    Ensure a modified Issue can have a field set to empty string
    '''
    # create modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)
    # supply a modified Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.assignee = ''

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == {'0.1', '0.2'}
    assert update_obj.merged_issue.assignee is None


@pytest.mark.parametrize('value_to_append', [0, 2])
def test_build_update__base_unmodified_and_updated_modified_to_append_to_set(value_to_append):
    '''
    Ensure an unmodified Issue can have a set field appended when it already has a value.

    This test ensures correct behaviour when the _ordering_ of a set changes during an append.

    The sets here use integers, as it's the simplest way to ensure a deterministic (and thus testable)
    order on the resulting set (https://stackoverflow.com/a/51949325/425050)
    '''
    # make a copy of ISSUE_1 fixture so it can modified without affecting other tests
    LOCAL_ISSUE_1 = copy.deepcopy(ISSUE_1)

    # set the starting Issue.fix_version value
    LOCAL_ISSUE_1['fix_versions'] = {1}

    # create unmodified base Issue fixture
    base_issue = Issue.deserialize(LOCAL_ISSUE_1)
    # supply a modified Issue fixture
    updated_issue = Issue.deserialize(LOCAL_ISSUE_1)
    updated_issue.fix_versions.add(value_to_append)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == set(LOCAL_ISSUE_1['fix_versions']) | {value_to_append}


@pytest.mark.parametrize('value_to_append', [0, 2])
def test_build_update__base_modified_and_updated_modified_to_append_to_set(value_to_append):
    '''
    Ensure an unmodified Issue can have a set field appended when it already has a value.

    This test ensures correct behaviour when the _ordering_ of a set changes during an append.

    The sets here use integers, as it's the simplest way to ensure a deterministic (and thus testable)
    order on the resulting set (https://stackoverflow.com/a/51949325/425050)
    '''
    # make a copy of ISSUE_1 fixture so it can modified without affecting other tests
    LOCAL_ISSUE_1 = copy.deepcopy(ISSUE_1)

    # set the starting Issue.fix_version value
    LOCAL_ISSUE_1['fix_versions'] = {1}

    # create unmodified base Issue fixture
    base_issue = Issue.deserialize(LOCAL_ISSUE_1)
    # supply a modified Issue fixture
    updated_issue = Issue.deserialize(LOCAL_ISSUE_1)
    updated_issue.fix_versions.add(value_to_append)

    update_obj = build_update(base_issue, updated_issue)

    assert update_obj.modified == {'fix_versions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fix_versions == set(LOCAL_ISSUE_1['fix_versions']) | {value_to_append}

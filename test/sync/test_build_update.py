from fixtures import (ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF, ISSUE_1_WITH_FIXVERSIONS_DIFF,
                      ISSUE_1_WITH_UPDATED_DIFF, ISSUE_NEW)
from jira_cli.models import Issue
from jira_cli.sync import Conflict, _build_update


def test_build_update__ignores_readonly_fields():
    '''
    Modified readonly fields must be ignored during build_update
    '''
    # create unmodified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # create modified issue as upstream (readonly field is only one modified)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_UPDATED_DIFF)

    update_obj = _build_update(base_issue, updated_issue)

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
    # create modified issue as updated
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = _build_update(base_issue, updated_issue)

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
    # create unmodified updated Issue fixture
    updated_issue = Issue.deserialize(ISSUE_1)

    update_obj = _build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_on_str_type_and_updated_modified_str_type_returns_conflict():
    '''
    Ensure conflict when (for str type):
      - base changed to field A="1"
      - updated changed to field A="2"
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # pass a conflicting modified Issue object (on assignee str)
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.assignee = 'murphye'

    update_obj = _build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee'}
    assert update_obj.conflicts == {
        'assignee': {'original': 'danil1', 'updated': 'murphye', 'base': 'hoganp'}
    }
    assert isinstance(update_obj.merged_issue.assignee, Conflict)


def test_build_update__base_modified_on_set_type_and_updated_modified_set_type_returns_conflict():
    '''
    Ensure conflict when (for set type):
      - base changed to field A={1,2}
      - updated changed to field A={1,3}
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_FIXVERSIONS_DIFF)
    # pass a conflicting modified Issue object (on fixVersions set)
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.fixVersions.add('0.3')

    update_obj = _build_update(base_issue, updated_issue)

    assert update_obj.modified == {'fixVersions'}
    assert update_obj.conflicts == {
        'fixVersions': {'original': ['0.1'], 'updated': ['0.1', '0.3'], 'base': ['0.1', '0.2']}
    }
    assert isinstance(update_obj.merged_issue.fixVersions, Conflict)


def test_build_update__base_nonconflict_changes_returned_in_merged_issue():
    '''
    Ensure base changes returned in merged output, along with a conflict when:
      - base changed to field A=1 and B=1
      - updated changed to field A=2
    '''
    # create a modified base Issue fixture, with an additional modified field
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    base_issue.summary = 'This is a test'
    # make a conflicting change on the updated issue
    updated_issue = Issue.deserialize(ISSUE_1)
    updated_issue.assignee = 'murphye'

    update_obj = _build_update(base_issue, updated_issue)

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

    update_obj = _build_update(base_issue, updated_issue)

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
    # create modified issue as updated
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = _build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'fixVersions'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.fixVersions == {'0.1', '0.2'}
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__base_modified_and_updated_modified_on_same_fields_with_same_value():
    '''
    Ensure NO conflict when:
      - base changed to field A=1
      - updated changed to field A=1
    '''
    # create a modified base Issue fixture
    base_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    # use the same modified Issue as updated (simulates the same change being made on both sides)
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = _build_update(base_issue, updated_issue)

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
    # make same change on single field on updated Issue
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    update_obj = _build_update(base_issue, updated_issue)

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
    # make same change, plus another different change on updated Issue
    updated_issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)
    updated_issue.summary = 'This is a test'

    update_obj = _build_update(base_issue, updated_issue)

    assert update_obj.modified == {'assignee', 'summary'}
    assert not update_obj.conflicts
    assert update_obj.merged_issue.summary == 'This is a test'
    assert update_obj.merged_issue.assignee == 'hoganp'


def test_build_update__new_issue():
    '''
    Validate return when calling _build_update with NEW issue
    '''
    # create a new Issue fixture
    new_issue = Issue.deserialize(ISSUE_NEW)

    # for new Issues created offline, the updated_issue is None
    update_obj = _build_update(new_issue, None)

    # modified fields should match all non-readonly fields
    assert update_obj.modified == set(['key', 'description', 'epic_ref', 'fixVersions', 'issuetype', 'project', 'reporter', 'summary'])
    assert not update_obj.conflicts
    for field in update_obj.modified:
        assert getattr(update_obj.merged_issue, field) == getattr(new_issue, field)

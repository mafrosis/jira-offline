'''
Tests for methods on the Issue model
'''
import copy
from unittest import mock

import pytest

from conftest import not_raises
from fixtures import ISSUE_1, ISSUE_NEW
from helpers import compare_issue_helper, modified_issue_helper
from jira_offline.exceptions import CannotSetIssueOriginalDirectly
from jira_offline.models import Issue


def test_issue_model__modified_is_false_after_constructor(project):
    '''
    Ensure Issue.modified is False after the object constructed
    '''
    issue = Issue.deserialize(ISSUE_1, project)
    assert issue.modified is False


def test_issue_model__modified_is_true_after_attribute_set(project):
    '''
    Ensure Issue.modified is set True when an attribute is set
    '''
    issue = Issue.deserialize(ISSUE_1, project)
    assert issue.modified is False

    issue.assignee = 'eggbert'
    assert issue.modified is True


def test_issue_model__blank_returns_valid_issue(project):
    '''
    Ensure Issue.blank returns a valid Issue with working methods
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    with not_raises(Exception):
        issue.diff()
        issue.serialize()
        issue.as_json()
        issue.render()


def test_issue_model__diff_returns_empty_for_unmodified_issue(project):
    '''
    Ensure Issue.diff returns empty list for an unmodified Issue
    '''
    issue = Issue.deserialize(ISSUE_1, project)
    assert issue.diff() == []


def test_issue_model__diff_returns_consistently_for_modified_issue(project):
    '''
    Ensure Issue.diff returns consistent diff for a modified Issue
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # modify the issue
    issue.assignee = 'eggbert'

    # validate the diff
    assert issue.diff() == [('change', 'assignee', ('eggbert', 'danil1'))]

    # serialize-deserialize roundtrip
    issue = Issue.deserialize(issue.serialize(), project)

    # re-validate the diff
    assert issue.diff() == [('change', 'assignee', ('eggbert', 'danil1'))]


def test_issue_model__original_is_set_after_constructor(project):
    '''
    Ensure Issue.original is set after the object constructed
    '''
    issue = Issue.deserialize(ISSUE_1, project)
    assert issue.original is not None


def test_issue_model__diff_sets_issue_diff_to_original(project):
    '''
    Ensure Issue.diff sets Issue.diff_to_original
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # modify the issue, and run a diff
    issue.assignee = 'eggbert'
    issue.diff()

    assert issue.diff_to_original == [('change', 'assignee', ('eggbert', 'danil1'))]


def test_issue_model__set_original_doesnt_set_modified_true(project):
    '''
    Ensure Issue.set_original does not set Issue.modified to true
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    issue.set_original(issue.serialize())

    assert issue.modified is False


def test_issue_model__set_original_removes_diff_to_original_field(project):
    '''
    Ensure Issue.set_original does not retain the Issue.diff_to_original field created by Issue.diff
    '''
    with mock.patch.dict(ISSUE_1, {'key': 'TEST-72'}):
        issue = modified_issue_helper(Issue.deserialize(ISSUE_1, project), assignee='hoganp')

    assert bool(issue.diff_to_original)

    issue.set_original(issue.serialize())

    assert 'diff_to_original' not in issue.original


def test_issue_model__setting_the_original_attribute_directly_raises_exception(project):
    '''
    Ensure setting Issue.original raises an exception
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    with pytest.raises(CannotSetIssueOriginalDirectly):
        issue.original = issue.serialize()


def test_issue_model__existing_issue_modified_set_true_during_attribute_set(project):
    '''
    Ensure Issue.modified is set to true by an attribute value change, if the Issue exists on Jira
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)
    setattr(issue_1, 'summary', 'egg')

    assert issue_1.modified is True


def test_issue_model__new_issue_modified_set_false_during_attribute_set(project):
    '''
    Ensure Issue.modified is set to true by an attribute value change, if the Issue exists on Jira
    '''
    issue_new = Issue.deserialize(ISSUE_NEW, project)
    setattr(issue_new, 'summary', 'egg')

    assert issue_new.modified is False


def test_issue_model__original_not_updated_during_attribute_set(project):
    '''
    Ensure Issue.original does not get modified by an attribute value change
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)
    serialized_issue = copy.deepcopy(issue_1.serialize())

    assert issue_1.original == serialized_issue

    setattr(issue_1, 'summary', 'egg')

    assert issue_1.original == serialized_issue


def test_issue_model__original_not_updated_during_attribute_set_with_roundtrip(mock_jira, project):
    '''
    Ensure Issue.original does not get modified by an attribute value change
    '''
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)
    serialized_issue = copy.deepcopy(mock_jira['TEST-71'].serialize())

    assert mock_jira['TEST-71'].original == serialized_issue

    setattr(mock_jira['TEST-71'], 'summary', 'egg')

    assert mock_jira['TEST-71'].original == serialized_issue


def test_issue_model__commit__produces_issue_with_diff(mock_jira, project):
    '''
    Ensure Issue.commit calls diff, and produces and results in a retrievable Issue with a diff
    '''
    mock_jira['TEST-71'] = issue = Issue.deserialize(ISSUE_1, project)

    issue.assignee = 'hoganp'

    with mock.patch('jira_offline.jira.jira', mock_jira):
        issue.commit()

    assert issue.assignee == 'hoganp'
    assert issue.diff() == [('change', 'assignee', ('hoganp', 'danil1'))]

    assert mock_jira['TEST-71'].assignee == 'hoganp'
    assert mock_jira['TEST-71'].diff() == [('change', 'assignee', ('hoganp', 'danil1'))]


def test_issue_model__commit__persists_edits(mock_jira, project):
    '''
    Ensure an Issue can have attributes set
    '''
    mock_jira['TEST-71'] = issue = Issue.deserialize(ISSUE_1, project)

    issue.assignee = 'hoganp'

    with mock.patch('jira_offline.jira.jira', mock_jira):
        issue.commit()

    assert issue.assignee == 'hoganp'
    assert mock_jira['TEST-71'].assignee == 'hoganp'


def test_issue_model__to_series_from_series_roundtrip(project):
    '''
    Ensure that Issue.to_series and Issue.from_series are behaving
    '''
    issue_1 = Issue.deserialize(ISSUE_1, project)

    roundtrip_issue = Issue.from_series(issue_1.to_series(), project)

    compare_issue_helper(issue_1, roundtrip_issue)


def test_issue_model__render_returns_core_fields(project):
    '''
    Validate Issue.render returns the set of core fields as used in `jira show`
    '''
    issue = Issue.deserialize(ISSUE_1, project)
    output = issue.render()

    assert output[0] == ('Summary', '[TEST-71] This is the story summary')
    assert output[1] == ('Type', 'Story')
    assert output[2] == ('Epic Link', 'TEST-1')
    assert output[3] == ('Status', 'Story Done')
    assert output[4] == ('Priority', 'Normal')
    assert output[5] == ('Assignee', 'danil1')
    assert output[6] == ('Story Points', '1')
    assert output[7] == ('Description', 'This is a story or issue')
    assert output[8] == ('Fix Version', '-  0.1')
    assert output[9] == ('Reporter', 'danil1')
    assert output[10] == ('Creator', 'danil1')


def test_issue_model__render_returns_core_does_not_include_space_prefix(project):
    '''
    Validate Issue.render DOES NOT return each row with a special spacer char as prefix, when not
    printing any modified fields
    '''
    issue = Issue.deserialize(ISSUE_1, project)
    output = issue.render()

    assert output[0][0][0] != '\u2800'
    assert output[len(output)-1][0][0] != '\u2800'


def test_issue_model__render_returns_optional_fields_only_when_set(project):
    '''
    Validate Issue.render returns the optional fields when they are set
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # Remove all optional fields created from the issue fixture
    issue.priority = None
    issue.assignee = None
    issue.story_points = None
    issue.description = None
    issue.fix_versions = None

    output = issue.render()

    assert output[0] == ('Summary', '[TEST-71] This is the story summary')
    assert output[1] == ('Type', 'Story')
    assert output[2] == ('Epic Link', 'TEST-1')
    assert output[3] == ('Status', 'Story Done')
    assert output[4] == ('Reporter', 'danil1')
    assert output[5] == ('Creator', 'danil1')


def test_issue_model__render_returns_extended_fields(project):
    '''
    Validate Issue.render includes extended customfields
    '''
    # Set an extended customfield on the issue
    with mock.patch.dict(ISSUE_1, {'extended': {'arbitrary_key': 'arbitrary_value'}}):
        issue = Issue.deserialize(ISSUE_1, project)

    output = issue.render()

    assert output[9] == ('Arbitrary Key', 'arbitrary_value')


def test_issue_model__render_returns_conflict(project):
    '''
    Validate Issue.render produces a git-style conflict for a specified field
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # Render assignee field as in-conflict
    output = issue.render(conflicts={'assignee': {'original': 'danil1', 'updated': 'hoganp', 'base': 'murphye'}})

    # Rendered output includes both sides of conflict with git-like formatting
    assert output[5] == ('<<<<<<< base', '')
    assert output[6] == ('Assignee', 'murphye')
    assert output[7] == ('=======', '')
    assert output[8] == ('Assignee', 'hoganp')
    assert output[9] == ('>>>>>>> updated', '')


def test_issue_model__render_returns_conflict_for_extended_fields(project):
    '''
    Validate Issue.render produces a git-style conflict for an extended customfield
    '''
    # Set an extended customfield on the issue
    with mock.patch.dict(ISSUE_1, {'extended': {'arbitrary_key': 'arbitrary_value'}}):
        issue = Issue.deserialize(ISSUE_1, project)

    # Render assignee field as in-conflict
    output = issue.render(
        conflicts={'extended.arbitrary_key': {
            'original': 'arbitrary_value', 'updated': 'upstream_value', 'base': 'other_value'
        }}
    )

    # Rendered output includes both sides of conflict with git-like formatting
    assert output[9] == ('<<<<<<< base', '')
    assert output[10] == ('Arbitrary Key', 'other_value')
    assert output[11] == ('=======', '')
    assert output[12] == ('Arbitrary Key', 'upstream_value')
    assert output[13] == ('>>>>>>> updated', '')


def test_issue_model__render_returns_modified_includes_space_prefix(project):
    '''
    Validate Issue.render returns each row with a special spacer char as prefix, to ensure printed
    fields line up vertically
    '''
    issue = Issue.deserialize(ISSUE_1, project)
    output = issue.render(modified_fields={'priority'})

    assert output[0][0][0] == '\u2800'
    assert output[len(output)-1][0][0] == '\u2800'


def test_issue_model__render_returns_modified_field_added(project):
    '''
    Validate Issue.render returns an added field with a "+" prefix
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # Add a new field on the issue
    issue.components = {'thing'}

    output = issue.render(modified_fields={'components'})

    # Rendered output is in colour with a "+" prefix
    assert output[9] == ('\x1b[32m+Components\x1b[0m', '\x1b[32m-  thing\x1b[0m')


def test_issue_model__render_returns_modified_field_removed(project):
    '''
    Validate Issue.render returns a removed field with a "-" prefix
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # Remove a field from the issue
    issue.description = None

    output = issue.render(modified_fields={'description'})

    # Rendered output is in colour with a "-" prefix
    assert output[7] == ('\x1b[31m-Description\x1b[0m', '\x1b[31mThis is a story or issue\x1b[0m')


def test_issue_model__render_returns_modified_field_changed(project):
    '''
    Validate Issue.render returns an added and removed rows, when a field is changed
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # Modify a field on the issue
    issue.description = 'New description'

    output = issue.render(modified_fields={'description'})

    # Rendered output is in colour, one line with a "-" prefix and another with a "+" prefix
    assert output[7] == ('\x1b[31m-Description\x1b[0m', '\x1b[31mThis is a story or issue\x1b[0m')
    assert output[8] == ('\x1b[32m+Description\x1b[0m', '\x1b[32mNew description\x1b[0m')


def test_issue_model__render_returns_modified_field_added_extended(project):
    '''
    Validate Issue.render returns an added extended customfield with a "+" prefix
    '''
    issue = Issue.deserialize(ISSUE_1, project)

    # Add a new extended customfield on the issue
    issue.extended['arbitrary_key'] = 'arbitrary_value'

    output = issue.render(modified_fields={'extended.arbitrary_key'})

    # Rendered output is in colour with a "+" prefix
    assert output[9] == ('\x1b[32m+Arbitrary Key\x1b[0m', '\x1b[32marbitrary_value\x1b[0m')


def test_issue_model__render_returns_modified_field_removed_extended(project):
    '''
    Validate Issue.render returns a removed extended customfield with a "-" prefix
    '''
    # Set an extended customfield on the issue
    with mock.patch.dict(ISSUE_1, {'extended': {'arbitrary_key': 'arbitrary_value'}}):
        issue = Issue.deserialize(ISSUE_1, project)

    # Remove a field from the issue
    issue.extended['arbitrary_key'] = None

    output = issue.render(modified_fields={'extended.arbitrary_key'})

    # Rendered output is in colour with a "-" prefix
    assert output[9] == ('\x1b[31m-Arbitrary Key\x1b[0m', '\x1b[31marbitrary_value\x1b[0m')


def test_issue_model__render_returns_modified_field_changed_extended(project):
    '''
    Validate Issue.render returns an added and removed rows, when an extended customfield is changed
    '''
    # Set an extended customfield on the issue
    with mock.patch.dict(ISSUE_1, {'extended': {'arbitrary_key': 'arbitrary_value'}}):
        issue = Issue.deserialize(ISSUE_1, project)

    # Modify a field on the issue
    issue.extended['arbitrary_key'] = 'updated_value'

    output = issue.render(modified_fields={'extended.arbitrary_key'})

    # Rendered output is in colour, one line with a "-" prefix and another with a "+" prefix
    assert output[9] == ('\x1b[31m-Arbitrary Key\x1b[0m', '\x1b[31marbitrary_value\x1b[0m')
    assert output[10] == ('\x1b[32m+Arbitrary Key\x1b[0m', '\x1b[32mupdated_value\x1b[0m')

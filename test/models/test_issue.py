'''
Tests for methods on the Issue model
'''
import pytest

from conftest import not_raises
from fixtures import ISSUE_1, ISSUE_1_WITH_ASSIGNEE_DIFF
from jira_offline.models import Issue


def test_issue_model__modified_is_false_after_constructor():
    '''
    Ensure Issue.modified is False after the object constructed
    '''
    issue = Issue.deserialize(ISSUE_1)
    assert issue.modified is False


def test_issue_model__modified_is_true_after_attribute_set():
    '''
    Ensure Issue.modified is set True when an attribute is set
    '''
    issue = Issue.deserialize(ISSUE_1)
    assert issue.modified is False

    issue.assignee = 'eggbert'
    assert issue.modified is True


def test_issue_model__blank_returns_valid_issue():
    '''
    Ensure Issue.blank returns a valid Issue with working methods
    '''
    issue = Issue.deserialize(ISSUE_1)

    with not_raises(Exception):
        issue.diff()
        issue.serialize()
        issue.as_json()
        issue.render()


def test_issue_model__diff_returns_empty_for_unmodified_issue():
    '''
    Ensure Issue.diff returns empty list for an unmodified Issue
    '''
    issue = Issue.deserialize(ISSUE_1)
    assert issue.diff() == []


def test_issue_model__diff_returns_consistently_for_modified_issue():
    '''
    Ensure Issue.diff returns consistent diff for a modified Issue
    '''
    issue = Issue.deserialize(ISSUE_1)

    # modify the issue
    issue.assignee = 'eggbert'

    # validate the diff
    assert issue.diff() == [('change', 'assignee', ('eggbert', 'danil1'))]

    # serialize-deserialize roundtrip
    issue = Issue.deserialize(issue.serialize())

    # re-validate the diff
    assert issue.diff() == [('change', 'assignee', ('eggbert', 'danil1'))]


def test_issue_model__original_is_set_after_constructor():
    '''
    Ensure Issue.original is set after the object constructed
    '''
    issue = Issue.deserialize(ISSUE_1)
    assert issue.original is not None


def test_issue_model__diff_sets_issue_diff_to_original():
    '''
    Ensure Issue.diff sets Issue.diff_to_original
    '''
    issue = Issue.deserialize(ISSUE_1)

    # modify the issue, and run a diff
    issue.assignee = 'eggbert'
    issue.diff()

    assert issue.diff_to_original == [('change', 'assignee', ('eggbert', 'danil1'))]


def test_issue_model__set_original_doesnt_set_modified_true():
    '''
    Ensure Issue.set_original does not set Issue.modified to true
    '''
    issue = Issue.deserialize(ISSUE_1)

    issue.set_original(issue.serialize())

    assert issue.modified is False


def test_issue_model__set_original_removes_diff_to_original_field():
    '''
    Ensure Issue.set_original does not retain the Issue.diff_to_original field created by Issue.diff
    '''
    issue = Issue.deserialize(ISSUE_1_WITH_ASSIGNEE_DIFF)

    assert bool(issue.diff_to_original)

    issue.set_original(issue.serialize())

    assert 'diff_to_original' not in issue.original


def test_issue_model__setting_the_original_attribute_directly_raises_exception():
    '''
    Ensure setting Issue.original raises an exception
    '''
    issue = Issue.deserialize(ISSUE_1)

    with pytest.raises(Exception):
        issue.original(issue.serialize())

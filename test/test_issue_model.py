from fixtures import ISSUE_1
from jira_cli.models import Issue


def test_issue_deserialize_setup():
    """
    Test deserialize sets the diff tracking fields on the Issue object
    """
    issue1 = Issue.deserialize(ISSUE_1)
    assert isinstance(issue1, Issue)
    assert isinstance(issue1.diff_to_original, list)
    assert isinstance(issue1.original, dict)


def test_issue_serialize_without_change_does_not_create_diff_property():
    """
    Test serialize of unchanged Issue object results in NO diff_to_original property
    """
    issue1 = Issue.deserialize(ISSUE_1)
    obj = issue1.serialize()

    # test diff_to_original field is NOT set
    assert not obj['diff_to_original']


def test_issue_serialize_with_change_creates_diff_property():
    """
    Test serialize of changed Issue object results in a diff_to_original property
    """
    issue1 = Issue.deserialize(ISSUE_1)
    # update a field on the Issue
    issue1.summary = 'TEST SUMMARY UPDATE'
    obj = issue1.serialize()

    # test diff_to_original field is set
    assert obj['diff_to_original']


def test_issue_serialized_original_matches_when_no_diff():
    """
    Test original property is same as Issue object if Issue is unchanged
    """
    issue1 = Issue.deserialize(ISSUE_1)
    obj = issue1.serialize()

    # remove diff_to_original property, as the reinflated original field does not have this ..
    del obj['diff_to_original']
    # .. everything else can be compared
    assert obj == issue1.original


def test_issue_serialized_original_does_not_match_when_diff():
    """
    Test original property is NOT same as Issue object if Issue is changed
    """
    issue1 = Issue.deserialize(ISSUE_1)
    # update a field on the Issue
    issue1.summary = 'TEST SUMMARY UPDATE'
    obj = issue1.serialize()

    # remove diff_to_original property, as the reinflated original field does not have this ..
    assert obj['diff_to_original']
    # .. everything else can be compared
    assert obj != issue1.original

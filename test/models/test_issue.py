import pytest

from jira_offline.exceptions import InvalidIssuePriority, InvalidIssueStatus
from jira_offline.models import Issue

from fixtures import ISSUE_1


def test_issue_model__status_property_fails_when_writing_invalid_value(project):
    '''
    Ensure that setting an Issue's status to an invalid value causes and exception
    '''
    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    with pytest.raises(InvalidIssueStatus):
        # set the status to an invalid value
        issue1.status = 'Bacon'


def test_issue_model__status_property_ok_when_writing_valid_value(project):
    '''
    Ensure that setting an Issue's status to a valid value succeeds
    '''
    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    # set the status to a valid value
    issue1.status = 'Done'
    assert issue1._status == 'Done'


def test_issue_model__priority_property_fails_when_writing_invalid_value(project):
    '''
    Ensure that setting an Issue's priority to an invalid value causes and exception
    '''
    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    with pytest.raises(InvalidIssuePriority):
        # set the priority to an invalid value
        issue1.priority = 'Bacon'


def test_issue_model__priority_property_ok_when_writing_valid_value(project):
    '''
    Ensure that setting an Issue's priority to a valid value succeeds
    '''
    # conftest fixture passes projects with priorities, and projects without
    # ignore the projects without priorities
    if not project.priorities:
        return

    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    # set the priority to a valid value
    issue1.priority = 'High'
    assert issue1._priority == 'High'


def test_issue_model__when_project_has_no_priorities_priority_property_fails_when_writing_any_value(project):
    '''
    Ensure that setting an Issue's priority to an invalid value causes and exception
    When the project does not have configured priorities
    '''
    # conftest fixture passes projects with priorities, and projects without
    # ignore the projects with priorities
    if project.priorities:
        return

    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    with pytest.raises(InvalidIssuePriority):
        # set the priority to an invalid value
        issue1.priority = 'Bacon'

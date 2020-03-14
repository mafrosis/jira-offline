import pytest

from jira_cli.exceptions import IssuePriorityInvalid
from jira_cli.models import Issue

from fixtures import ISSUE_1


def test_issue_model__priority_property_fails_when_writing_invalid_value(project):
    '''
    Ensure that setting an Issue's priority to an invalid value causes and exception
    '''
    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    with pytest.raises(IssuePriorityInvalid):
        # set the priority to an invalid value
        issue1.priority = 'Bacon'


def test_issue_model__priority_property_ok_when_writing_valid_value(project):
    '''
    Ensure that setting an Issue's priority to a value value succeeds
    '''
    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    # set the priority to a valid value
    issue1.priority = 'High'
    assert issue1._priority == 'High'  # pylint: disable=no-member

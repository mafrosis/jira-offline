from unittest import mock

import pytest

from jira_offline.exceptions import InvalidIssuePriority, InvalidIssueStatus, UnableToCopyCustomCACert
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
    assert issue1._status == 'Done'  # pylint: disable=no-member


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
    # deserialize a fixture into an Issue object
    issue1 = Issue.deserialize(ISSUE_1, project_ref=project)

    # set the priority to a valid value
    issue1.priority = 'High'
    assert issue1._priority == 'High'  # pylint: disable=no-member


@mock.patch('jira_offline.models.shutil')
@mock.patch('jira_offline.models.click')
@mock.patch('jira_offline.models.pathlib')
def test_project_meta_model__set_ca_cert__calls_copyfile_with_path(mock_pathlib, mock_click, mock_shutil, project):
    '''
    Validate shutil.copyfile is called with file path
    '''
    mock_click.get_app_dir.return_value = '/tmp'
    project.set_ca_cert('/tmp/ca.pem')

    mock_shutil.copyfile.assert_called_with('/tmp/ca.pem', '/tmp/99fd9182cfc4c701a8a662f6293f4136201791b4.ca_cert')


@mock.patch('jira_offline.models.shutil')
@mock.patch('jira_offline.models.click')
@mock.patch('jira_offline.models.pathlib')
def test_project_meta_model__set_ca_cert__handles_failed_copy(mock_pathlib, mock_click, mock_shutil, project):
    '''
    Validate shutil.copyfile is called with file path
    '''
    mock_click.get_app_dir.return_value = '/tmp'
    mock_shutil.copyfile.side_effect = IOError

    with pytest.raises(UnableToCopyCustomCACert):
        project.set_ca_cert('/tmp/ca.pem')

from unittest import mock

import pytest

from jira_offline.exceptions import UnableToCopyCustomCACert


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

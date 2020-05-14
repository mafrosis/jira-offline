'''
Tests for general util functions from utils.__init__ module
'''
import pytest

from jira_offline.exceptions import ProjectNotConfigured
from jira_offline.models import ProjectMeta
from jira_offline.utils import find_project


def test_find_project__returns_projectmeta_object(mock_jira):
    '''
    Ensure find_project returns the correct ProjectMeta object
    '''
    project = find_project(mock_jira, 'TEST')
    assert isinstance(project, ProjectMeta)
    assert project.key == 'TEST'
    assert project.username == 'test'
    assert project.password == 'dummy'


def test_find_project__raises_when_projectkey_not_found(mock_jira):
    '''
    Ensure find_project raises ProjectNotConfigured for an invalid projectkey
    '''
    with pytest.raises(ProjectNotConfigured):
        find_project(mock_jira, 'UNKNOWN')

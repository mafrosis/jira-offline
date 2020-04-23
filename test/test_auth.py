from unittest import mock

import pytest

from jira_offline.auth import authenticate, get_user_creds
from jira_offline.models import ProjectMeta


@mock.patch('jira_offline.auth.get_user_creds')
@mock.patch('jira_offline.auth.oauth_dance')
@mock.patch('builtins.open')
def test_authenticate__calls_oauth_dance_when_oauth_params_passed(mock_open, mock_oauth_dance, mock_get_user_creds):
    '''
    Ensure the private key file is opened and oauth_dance() is called when params passed
    '''
    project_meta = ProjectMeta(key='test')

    authenticate(project_meta, oauth_consumer_key='egg', oauth_private_key_path='pky')

    mock_open.assert_called_with('pky')
    mock_oauth_dance.assert_called_with(project_meta, 'egg', mock_open.return_value.__enter__.return_value.read.return_value)
    assert not mock_get_user_creds.called


@mock.patch('jira_offline.auth.get_user_creds')
@mock.patch('jira_offline.auth.oauth_dance')
@mock.patch('jira_offline.auth._test_jira_connect')
@mock.patch('jira_offline.auth.click')
def test_authenticate__calls_get_user_creds_when_username_passed(mock_click, mock_test_jira_connect, mock_oauth_dance, mock_get_user_creds):
    '''
    Ensure get_user_creds() is called when params passed
    '''
    project_meta = ProjectMeta(key='test')

    authenticate(project_meta, username='egg', password='bacon')

    assert not mock_oauth_dance.called
    mock_get_user_creds.assert_called_with(project_meta, 'egg', 'bacon')


@pytest.mark.parametrize('project_meta', [
    ProjectMeta(key='test'),
    ProjectMeta(key='test', username='test', password='dummy'),
])
@mock.patch('jira_offline.auth._test_jira_connect')
@mock.patch('jira_offline.auth.click')
def test_get_user_creds__calls_click_prompt_and_jira_connect(mock_click, mock_test_jira_connect, project_meta):
    '''
    Ensure that get_user_creds() makes calls to click.prompt and Jira.connect()
    '''
    # mock return from user CLI prompts
    mock_click.prompt.return_value = 'egg'

    get_user_creds(project_meta)

    assert mock_click.prompt.call_count == 2
    assert project_meta.username == 'egg'
    assert project_meta.password == 'egg'
    assert mock_test_jira_connect.called


@mock.patch('jira_offline.auth._test_jira_connect')
@mock.patch('jira_offline.auth.click')
def test_get_user_creds__calls_prompt_only_once_when_username_passed(mock_click, mock_test_jira_connect):
    '''
    Ensure that get_user_creds() only calls click.prompt once when username param is passed
    '''
    project_meta = ProjectMeta(key='test')

    # mock return from user CLI prompts
    mock_click.prompt.return_value = 'egg'

    get_user_creds(project_meta, username='bacon')

    assert mock_click.prompt.call_count == 1
    assert project_meta.username == 'bacon'
    assert project_meta.password == 'egg'

from unittest import mock

from click.testing import CliRunner

from jira_offline.cli import cli
from jira_offline.models import ProjectMeta


def test_cli_project_delete__success(mock_jira):
    '''
    Ensure success when deleting a project
    '''
    # Setup a test project fixture
    new_project = ProjectMeta.factory('http://example.com/DELETEME')
    mock_jira.config.projects[new_project.id] = new_project

    runner = CliRunner(mix_stderr=False)

    # Validate fixture before test call
    assert new_project.id in mock_jira.config.projects

    with mock.patch('jira_offline.cli.project.jira', mock_jira):
        result = runner.invoke(cli, ['project', 'delete', 'DELETEME'])

    assert result.exit_code == 0, result.output
    assert new_project.id not in mock_jira
    assert mock_jira.config.write_to_disk.called


@mock.patch('jira_offline.auth._test_jira_connect')
def test_cli_project_update_auth__can_update_password(mock_test_jira_connect, mock_jira):
    '''
    Ensure success when changing a username/password
    '''
    # Setup a test project fixture
    new_project = ProjectMeta.factory('http://example.com/EDITME')
    new_project.username = 'dave'
    new_project.password = 'eggs'
    mock_jira.config.projects[new_project.id] = new_project

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.project.jira', mock_jira):
        result = runner.invoke(cli, ['project', 'update-auth', 'EDITME', '--username', 'bob', '--password', 'bacon'])

    assert result.exit_code == 0, result.output
    assert new_project.username == 'bob'
    assert new_project.password == 'bacon'
    assert mock_test_jira_connect.called
    assert mock_jira.config.write_to_disk.called

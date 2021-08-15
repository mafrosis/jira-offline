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

    runner = CliRunner()

    # Validate fixture before test call
    assert new_project.id in mock_jira.config.projects

    with mock.patch('jira_offline.cli.project.jira', mock_jira):
        result = runner.invoke(cli, ['project', 'delete', 'DELETEME'])

    assert result.exit_code == 0, result.stdout
    assert new_project.id not in mock_jira
    assert mock_jira.config.write_to_disk.called

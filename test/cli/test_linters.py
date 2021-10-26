from unittest import mock

from click.testing import CliRunner
import pytest

from fixtures import ISSUE_1
from jira_offline.cli import cli
from jira_offline.jira import Issue


LINT_SUBCOMMANDS = [
    'fix-versions',
    'issues-missing-epic',
]


@pytest.mark.parametrize('subcommand', LINT_SUBCOMMANDS)
def test_lint_smoketest(mock_jira, project, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache has a
    single issue
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['lint', subcommand])

    # CLI should always exit zero
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize('subcommand', LINT_SUBCOMMANDS)
def test_lint_smoketest_empty(mock_jira, subcommand):
    '''
    Dumb smoke test function to check for errors via CLI - when the jira-offline issue cache is empty
    '''
    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.linters.jira', mock_jira):
        result = runner.invoke(cli, ['lint', subcommand])

    # CLI should always exit 1
    assert result.exit_code == 1, result.output


@mock.patch('jira_offline.cli.linters.lint_fix_versions')
def test_cli_lint__fix_versions__echo(mock_lint_fix_versions, mock_jira, project):
    '''
    Ensure lint fix-versions command calls click.echo without error
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['lint', 'fix-versions'])

    assert result.exit_code == 0, result.output
    assert mock_lint_fix_versions.called
    assert 'issues missing the fix_versions field' in result.stdout


@mock.patch('jira_offline.cli.linters.lint_fix_versions')
def test_cli_lint__fix_versions__fix_requires_words(mock_lint_fix_versions, mock_jira, project):
    '''
    Ensure lint fix-versions with --fix param errors without --value
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['lint', '--fix', 'fix-versions'])

    assert result.exit_code != 0, result.stdout
    assert 'You must pass --value with --fix' in result.stderr


@mock.patch('jira_offline.cli.linters.lint_fix_versions')
def test_cli_lint__fix_versions__fix_passes_words_to_lint_func(mock_lint_fix_versions, mock_jira, project):
    '''
    Ensure lint fix-versions with --fix and --value calls lint_fix_versions
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['lint', '--fix', 'fix-versions', '--value', '0.1'])

    assert result.exit_code == 0, result.output
    mock_lint_fix_versions.assert_called_with(fix=True, value='0.1')


@mock.patch('jira_offline.cli.linters.lint_issues_missing_epic')
def test_cli_lint__issues_missing_epic__echo(mock_lint_issues_missing_epic, mock_jira, project):
    '''
    Ensure lint issues_missing_epic command calls click.echo without error
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['lint', 'issues-missing-epic'])

    assert result.exit_code == 0, result.output
    assert mock_lint_issues_missing_epic.called
    assert 'issues missing an epic' in result.stdout


@mock.patch('jira_offline.cli.linters.lint_issues_missing_epic')
def test_cli_lint__issues_missing_epic__fix_requires_epic_link(mock_lint_issues_missing_epic, mock_jira, project):
    '''
    Ensure lint issues_missing_epic with --fix param errors without --epic-link
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['lint', '--fix', 'issues-missing-epic'])

    assert result.exit_code != 0, result.stdout
    assert result.stderr.endswith('You must pass --epic_link with --fix\n')


@mock.patch('jira_offline.cli.linters.lint_issues_missing_epic')
def test_cli_lint__issues_missing_epic__fix_passes_epic_link_to_lint_func(
        mock_lint_issues_missing_epic, mock_jira, project
    ):
    '''
    Ensure lint issues-missing-epic with --fix and --epic_link calls lint_issues_missing_epic
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    runner = CliRunner(mix_stderr=False)

    with mock.patch('jira_offline.cli.linters.jira', mock_jira), \
            mock.patch('jira_offline.jira.jira', mock_jira):
        result = runner.invoke(cli, ['lint', '--fix', 'issues-missing-epic', '--epic-link', 'TEST'])

    assert result.exit_code == 0, result.output
    mock_lint_issues_missing_epic.assert_called_with(fix=True, epic_link='TEST')

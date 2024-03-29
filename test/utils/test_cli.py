from unittest import mock

import click
import pytest

from conftest import not_raises
from fixtures import ISSUE_1
from jira_offline.jira import Issue
from jira_offline.cli.utils import CustomfieldsAsOptions, prepare_df, ValidCustomfield


def test_print_list__display_ls_fields_config_rendered_in_listing(mock_jira, project):
    '''
    Ensure the specified ls fields are rendered in the print_list output, when user config option IS
    configured
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    mock_jira.config.user_config.display.ls_fields = {'summary'}

    with mock.patch('jira_offline.cli.utils.jira', mock_jira), \
        mock.patch('jira_offline.jira.jira', mock_jira):
        df = prepare_df(mock_jira.df)

    assert set(df.columns) == {'summary'}


def test_print_list__display_ls_fields_defaults_rendered_in_listing(mock_jira, project):
    '''
    Ensure the default ls fields are rendered in the print_list output, when user config option IS NOT
    configured
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1, project)

    with mock.patch('jira_offline.cli.utils.jira', mock_jira), \
        mock.patch('jira_offline.jira.jira', mock_jira):
        df = prepare_df(mock_jira.df)

    assert set(df.columns) == set(['issuetype', 'epic_link', 'summary', 'status', 'assignee', 'updated'])


@mock.patch('jira_offline.cli.utils.ValidCustomfield')
def test_click_customfieldsasoptions__configured_customfields_become_options(mock_ValidCustomfield, mock_jira):
    '''
    Ensure ValidCustomfield click.Command instances are created for configured customfields
    '''
    mock_jira.config.user_config.customfields = {'*': {'arbitrary-user-defined-field': 'customfield_10400'}}

    # Fixture for a click CLI command
    # Key "params" is set of global options defined in `jira_offline.cli.global_options`
    kwargs = {'name': 'new', 'params': ['--config', '--verbose', '--debug']}

    assert len(kwargs['params']) == 3

    with mock.patch('jira_offline.cli.utils.jira', mock_jira):
        CustomfieldsAsOptions(*tuple(), **kwargs)

    assert mock_ValidCustomfield.called_once_with(['--epic-link'], '')
    assert mock_ValidCustomfield.called_once_with(['--epic-name'], '')
    assert mock_ValidCustomfield.called_once_with(['--sprint'], '')
    assert mock_ValidCustomfield.called_once_with(['--arbitrary-user-defined-field'], '')


@mock.patch('jira_offline.cli.utils._get_project')
@mock.patch('jira_offline.cli.utils._get_issue')
def test_validcustomfield__calls_get_issue_when_key_supplied(mock_validcustomfield_get_issue, mock_validcustomfield_get_project, mock_jira):
    '''
    Ensure `ValidCustomfield.handle_parse_result` calls `_get_issue`, when an issue key is supplied
    '''
    # CLI options
    opts = {
        'key': 'TEST-1',  # The `edit` command called for issue TEST-1
    }

    command = CustomfieldsAsOptions(*tuple(), **{'name': 'edit', 'params': []})

    with mock.patch('jira_offline.cli.utils.jira', mock_jira):
        ValidCustomfield(
            ['--arbitrary-user-defined-field'], help=''
        ).handle_parse_result(
            click.core.Context(command), opts, None
        )

    assert mock_jira.load_issues.called
    assert mock_validcustomfield_get_issue.called
    assert not mock_validcustomfield_get_project.called


@mock.patch('jira_offline.cli.utils._get_project')
@mock.patch('jira_offline.cli.utils._get_issue')
def test_validcustomfield_calls__get_project_when_projectkey_supplied(mock_validcustomfield_get_issue, mock_validcustomfield_get_project, mock_jira):
    '''
    Ensure `ValidCustomfield.handle_parse_result` calls `_get_project`, when a project key is supplied
    '''
    # CLI options
    opts = {
        'projectkey': 'TEST',  # The `new` command called against project TEST
    }

    command = CustomfieldsAsOptions(*tuple(), **{'name': 'edit', 'params': []})

    with mock.patch('jira_offline.cli.utils.jira', mock_jira):
        ValidCustomfield(
            ['--arbitrary-user-defined-field'], help=''
        ).handle_parse_result(
            click.core.Context(command), opts, None
        )

    assert not mock_jira.load_issues.called
    assert not mock_validcustomfield_get_issue.called
    assert mock_validcustomfield_get_project.called


def test_validcustomfield__raises_error_on_customfield_supplied_but_not_mapped_to_project(mock_jira):
    '''
    Ensure a customfield parameter passed on the CLI causes an error, if that customfield does not
    exist on the specified project
    '''
    # Setup the app config with a customfield.. which is not mapped to project TEST
    mock_jira.config.user_config.customfields = {'*': {'arbitrary-user-defined-field': 'customfield_10400'}}

    # CLI options
    opts = {
        'projectkey': 'TEST',                    # The `new` command called against project TEST
        'arbitrary-user-defined-field': 'TEST',  # Param --arbitrary-user-defined-field passed to `new`
    }

    command = CustomfieldsAsOptions(*tuple(), **{'name': 'new', 'params': []})

    with mock.patch('jira_offline.cli.utils.jira', mock_jira):
        with pytest.raises(click.exceptions.UsageError):
            ValidCustomfield(
                ['--arbitrary-user-defined-field'], help=''
            ).handle_parse_result(
                click.core.Context(command), opts, None
            )


def test_validcustomfield__succeeds_on_customfield_supplied_and_mapped_to_project(mock_jira, project):
    '''
    Ensure a customfield parameter passed on the CLI does not cause an error, if that customfield
    exists on the specified project
    '''
    # Setup the app config with a customfield..
    mock_jira.config.user_config.customfields = {'*': {'arbitrary-user-defined-field': 'customfield_10400'}}
    # .. Add that customfield to project TEST
    project.customfields.extended = {'arbitrary-user-defined-field': 'customfield_10400'}

    # CLI options
    opts = {
        'projectkey': 'TEST',                    # The `new` command called against project TEST
        'arbitrary-user-defined-field': 'TEST',  # Param --arbitrary-user-defined-field passed to `new`
    }

    command = CustomfieldsAsOptions(*tuple(), **{'name': 'new', 'params': []})

    with mock.patch('jira_offline.cli.utils.jira', mock_jira):
        with not_raises(click.exceptions.UsageError):
            ValidCustomfield(
                ['--arbitrary-user-defined-field'], help=''
            ).handle_parse_result(
                click.core.Context(command), opts, None
            )

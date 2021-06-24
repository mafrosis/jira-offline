from unittest import mock

from fixtures import ISSUE_1
from jira_offline.jira import Issue
from jira_offline.utils.cli import print_list


def test_print_list__display_ls_fields_config_rendered_in_listing(mock_jira):
    '''
    Ensure the specified ls fields are rendered in the print_list output, when user config option IS
    configured
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    mock_jira.config.display.ls_fields = {'key'}

    with mock.patch('jira_offline.utils.cli.jira', mock_jira), \
        mock.patch('jira_offline.jira.jira', mock_jira):
        df = print_list(mock_jira.df)

    assert set(df.columns) == {'key'}


def test_print_list__display_ls_fields_defaults_rendered_in_listing(mock_jira):
    '''
    Ensure the default ls fields are rendered in the print_list output, when user config option IS NOT
    configured
    '''
    # add fixture to Jira dict
    mock_jira['TEST-71'] = Issue.deserialize(ISSUE_1)

    with mock.patch('jira_offline.utils.cli.jira', mock_jira), \
        mock.patch('jira_offline.jira.jira', mock_jira):
        df = print_list(mock_jira.df)

    assert set(df.columns) == set(['issuetype', 'epic_ref', 'summary', 'status', 'assignee', 'updated'])

from unittest import mock

from fixtures import ISSUE_1, ISSUE_2
from jira_cli.main import Issue


@mock.patch('jira_cli.main.tqdm')
def test_pull_issues_calls__connect(mock_tqdm, mock_jira):
    """
    Ensure pull_issues() method calls _connect()
    """
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    mock_jira.pull_issues()
    assert mock_jira._connect.called


@mock.patch('jira_cli.main.tqdm')
def test_pull_issues_last_updated_field_creates_filter_query(mock_tqdm, mock_jira):
    """
    Test config.last_updated being set causes a filtered query from value of last_updated
    """
    mock_jira.config.last_updated = '2019-01-01 00:00'
    mock_jira.load_issues = mock.Mock()
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    mock_jira.pull_issues()

    # first calls, args (not kwargs), first arg
    assert mock_jira._jira.search_issues.call_args_list[0][0][0] == 'project IN (CNTS) AND updated > "2019-01-01 00:00"'


@mock.patch('jira_cli.main.tqdm')
def test_pull_issues_last_updated_field_causes_filter_from_waaay_back(mock_tqdm, mock_jira):
    """
    Test config.last_updated NOT being set causes a filtered query from 2010-01-01
    """
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    mock_jira.pull_issues()

    # first calls, args (not kwargs), first arg
    assert mock_jira._jira.search_issues.call_args_list[0][0][0] == 'project IN (CNTS) AND updated > "2010-01-01 00:00"'


@mock.patch('jira_cli.main.tqdm')
def test_pull_issues_write_issues_and_config_called(mock_tqdm, mock_jira):
    """
    Test write_issues method is called
    Test config.write_to_disk method is called
    """
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    mock_jira.pull_issues()
    assert mock_jira.config.write_to_disk.called


@mock.patch('jira_cli.main.tqdm')
def test_pull_issues_adds_issues_to_self(mock_tqdm, mock_jira):
    """
    As jira class implements dict, ensure that issues returned by search_issues() are added to the dict
    """
    # mock Jira API to return two issues
    issues = [Issue.deserialize(ISSUE_1), Issue.deserialize(ISSUE_2)]
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), issues, []]
    mock_jira._raw_issue_to_object = mock.Mock(side_effect=issues)

    assert len(mock_jira.keys()) == 0
    mock_jira.pull_issues()
    assert len(mock_jira.keys()) == 2

from unittest import mock

from fixtures import ISSUE_1, ISSUE_2
from jira_cli.models import Issue
from jira_cli.sync import pull_issues


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__calls_connect(mock_tqdm, mock_jira):
    """
    Ensure pull_issues() method calls connect()
    """
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    pull_issues(mock_jira)
    assert mock_jira.connect.called


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__last_updated_field_creates_filter_query(mock_tqdm, mock_jira):
    """
    Test config.last_updated being set causes a filtered query from value of last_updated
    """
    mock_jira.config.last_updated = '2019-01-01 00:00'
    mock_jira.load_issues = mock.Mock()
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    pull_issues(mock_jira)

    # first calls, args (not kwargs), first arg
    assert mock_jira._jira.search_issues.call_args_list[0][0][0] == 'project IN (CNTS) AND updated > "2019-01-01 00:00"'


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__last_updated_field_causes_filter_from_waaay_back(mock_tqdm, mock_jira):
    """
    Test config.last_updated NOT being set causes a filtered query from 2010-01-01
    """
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    pull_issues(mock_jira)

    # first calls, args (not kwargs), first arg
    assert mock_jira._jira.search_issues.call_args_list[0][0][0] == 'project IN (CNTS) AND updated > "2010-01-01 00:00"'


@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__write_issues_and_config_called(mock_tqdm, mock_jira):
    """
    Test write_issues method is called
    Test config.write_to_disk method is called
    """
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), []]

    pull_issues(mock_jira)
    assert mock_jira.config.write_to_disk.called


@mock.patch('jira_cli.sync._raw_issue_to_object')
@mock.patch('jira_cli.sync.tqdm')
def test_pull_issues__adds_issues_to_self(mock_tqdm, mock_raw_issue_to_object, mock_jira):
    """
    As jira class implements dict, ensure that issues returned by search_issues() are added to the dict
    """
    # mock Jira API to return two issues
    issues = [Issue.deserialize(ISSUE_1), Issue.deserialize(ISSUE_2)]
    mock_jira._jira.search_issues.side_effect = [mock.Mock(total=1), issues, []]

    mock_raw_issue_to_object.side_effect = issues

    assert len(mock_jira.keys()) == 0
    pull_issues(mock_jira)
    assert len(mock_jira.keys()) == 2

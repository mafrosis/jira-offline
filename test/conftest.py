from unittest import mock

import jira as mod_jira
import pytest

from jira_cli.config import AppConfig
from jira_cli.main import Jira


@pytest.fixture()
def mock_jira():
    """
    Return a basic mock for the core Jira class.

    - Mock the config object with some dummy data
    - Mock the config object from writing to disk
    - Mock the pypi jira module's Jira object. Consuming tests can mock individual methods as
      necessary
    - Mock the _connect method
    - Mock the write_issues method
    """
    jira = Jira()
    jira.config = AppConfig(username='test', password='dummy', projects={'CNTS'})
    jira.config.write_to_disk = mock.Mock()
    jira._connect = mock.Mock()
    jira._jira = mock.Mock(spec=mod_jira.JIRA)
    jira.write_issues = mock.Mock()
    # monkey patch load_issues to only return the DataFrame representation of current dict
    jira.load_issues = lambda: jira.df
    return jira

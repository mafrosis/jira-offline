from unittest import mock

import jira as mod_jira
import pytest

from jira_cli.config import AppConfig
from jira_cli.main import Jira


@pytest.fixture()
def mock_jira():
    '''
    Return a basic mock for the core Jira class.

    - Mock the config object with some dummy data
    - Mock the config object from writing to disk
    - Mock the pypi jira module's Jira object. Consuming tests can mock individual methods as
      necessary
    - Mock the connect method
    - Mock the write_issues method
    '''
    jira = Jira()
    jira.config = AppConfig(username='test', password='dummy', projects={'CNTS'})
    jira.config.write_to_disk = mock.Mock()
    jira._jira = mock.Mock(spec=mod_jira.JIRA)
    jira.connect = mock.Mock(return_value=jira._jira)
    jira.write_issues = mock.Mock()
    jira.load_issues = mock.Mock()
    jira.update_issue = mock.Mock()
    return jira

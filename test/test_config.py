from unittest import mock

from jira_offline.config import load_config


@mock.patch('jira_offline.config.AppConfig')
@mock.patch('jira_offline.config.os')
@mock.patch('jira_offline.config.click')
def test_load_config__config_created_when_no_config_file_exists(mock_click, mock_os, mock_appconfig_class):
    '''
    Test that when no config file exists, an AppConfig object is created
    '''
    # config file does not exist
    mock_os.path.exists.return_value = False

    load_config()

    assert mock_appconfig_class.called  # class instantiated

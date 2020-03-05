'''
This module contains functions for authenticating a user against a Jira server
'''
from typing import Optional

import click
import requests

from jira_cli import __title__
from jira_cli.exceptions import FailedAuthError
from jira_cli.models import AppConfig


def authenticate(config: AppConfig, protocol: str, hostname: str, username: Optional[str]=None):
    '''
    Authenticate against hostname with either basic-auth or oAuth

    Params:
        config:                  Dependency-injected application config object
        protocol:                Protocol to use connecting to Jira (http/https)
        hostname:                Hostname of the Jira server (including port if non-standard)
        username:                Basic auth username
    '''
    # store the Jira server protocol and hostname
    config.protocol = protocol
    config.hostname = hostname

    # ask for password and validate creds
    get_user_creds(config, username)

    # on successful authentication to Jira API; write config to local file
    config.write_to_disk()


def get_user_creds(config: AppConfig, username: Optional[str]=None):
    '''
    Accept username/password and validate against Jira server

    Params:
        config:    Dependency-injected application config object
        username:  Basic auth username
    '''
    config.username = username
    if not config.username:
        config.username = click.prompt('Username', type=str)

    config.password = click.prompt('Password', type=str, hide_input=True)

    # validate Jira connection details
    if config.username and config.password:
        if not _test_jira_connect(config):
            raise FailedAuthError(config.hostname)


def _test_jira_connect(config: AppConfig):
    '''Test connection to Jira API to validate config object credentials'''
    try:
        # late import of Jira class to prevent cyclic-import
        from jira_cli.main import Jira  # pylint: disable=import-outside-toplevel,cyclic-import
        Jira().connect(config)
        return True
    except requests.exceptions.ConnectionError:
        return False

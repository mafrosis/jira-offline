'''
This module contains functions and data structures for managing application config
'''
import json
import os
import logging
import sys
from typing import Optional

import click
import requests

from jira_cli import __title__
from jira_cli.models import AppConfig


logger = logging.getLogger('jira')


def load_config():
    '''
    Load app configuration from local JSON file
    '''
    config_filepath = os.path.join(click.get_app_dir(__title__), 'app.json')

    config: Optional[AppConfig] = None

    if os.path.exists(config_filepath):
        try:
            with open(config_filepath) as f:
                config = AppConfig.deserialize(json.load(f))
        except IsADirectoryError:
            logger.error('There is a directory at config path (%s)!', config_filepath)
            sys.exit(1)
        except ValueError:
            logger.error('Bad JSON in config file; ignoring')

    if not config:
        config = AppConfig()

    return config


def get_user_creds(config: AppConfig):
    '''
    Accept username/password and validate against Jira server

    Params:
        config:    Dependency-injected application config object
    '''
    config.username = click.prompt('Username', type=str)
    config.password = click.prompt('Password', type=str, hide_input=True)

    # validate Jira connection details, when creds change
    if config.username and config.password:
        if _test_jira_connect(config):

            # on successful connect to JIRA API; write config to local file
            config.write_to_disk()
        else:
            logger.error('Failed connecting to %s', config.hostname)
            config.hostname = None


def _test_jira_connect(config: AppConfig):
    '''Test connection to Jira API to validate config object credentials'''
    try:
        # late import of Jira class to prevent cyclic-import
        from jira_cli.main import Jira  # pylint: disable=import-outside-toplevel,cyclic-import
        Jira().connect(config)
        return True
    except requests.exceptions.ConnectionError:
        return False

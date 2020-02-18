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
from jira_cli.main import Jira
from jira_cli.models import AppConfig


logger = logging.getLogger('jira')


def load_config(prompt_for_creds: bool=False):
    '''
    Load app configuration from local JSON file

    Params:
        prompt_for_creds:  Force a re-prompt for Jira credentials
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
        prompt_for_creds = True

    if prompt_for_creds:
        _get_user_creds(config)

    return config


def _get_user_creds(config: AppConfig):
    config.username = click.prompt('Username', type=str)
    config.password = click.prompt('Password', type=str, hide_input=True)

    # validate Jira connection details, when creds change
    if config.username and config.password:
        try:
            Jira().connect(config)  # pylint: disable=protected-access

            # on successful connect to JIRA API; write config to local file
            config.write_to_disk()

        except requests.exceptions.ConnectionError:
            logger.error('Failed connecting to %s', config.hostname)
            config.hostname = None

'''
This module contains functions and data structures for managing application config
'''
from dataclasses import dataclass, field
import json
import os
import logging
import sys
from typing import Dict, Optional

import click
import requests

from jira_cli import __title__
from jira_cli.main import Jira
from jira_cli.models import DataclassSerializer, ProjectMeta


logger = logging.getLogger('jira')


@dataclass
class AppConfig(DataclassSerializer):
    username: Optional[str] = field(default=None)
    password: Optional[str] = field(default=None)
    hostname: Optional[str] = field(default='jira.atlassian.com')
    last_updated: Optional[str] = field(default=None)
    projects: Dict[str, ProjectMeta] = field(default_factory=dict)

    def write_to_disk(self):
        config_filepath = os.path.join(click.get_app_dir(__title__), 'app.json')
        with open(config_filepath, 'w') as f:
            json.dump(self.serialize(), f)


def load_config(projects: set=None, prompt_for_creds: bool=False):
    '''
    Load app configuration from local JSON file

    Params:
        projects:          List of Jira project keys
        prompt_for_creds:  Force a re-prompt for Jira credentials
    '''
    config_filepath = os.path.join(click.get_app_dir(__title__), 'app.json')

    config: Optional[AppConfig] = None

    if os.path.exists(config_filepath):
        try:
            with open(config_filepath) as f:
                config = AppConfig.deserialize(json.load(f))
        except IsADirectoryError:
            logger.error('There is directory at config path (%s)!', config_filepath)
            sys.exit(1)
        except ValueError:
            logger.error('Bad JSON in config file; ignoring')

    if not config:
        config = AppConfig()
        prompt_for_creds = True

    if prompt_for_creds:
        _get_user_creds(config)

    if projects:
        # if projects is passed on the CLI, merge it into the config
        config.projects.update(projects)
        logger.info('Working with projects %s', ','.join(config.projects))

    if not config.projects:
        # abort if when there are no projects to work with!
        logger.error('No projects cached, or passed with --projects')
        sys.exit(1)

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

from dataclasses import dataclass, field
import json
import os
import getpass
import logging
from pathlib import Path
import sys

import requests

from jira_cli.main import DataclassSerializer, Jira


logger = logging.getLogger('jira')


@dataclass
class AppConfig(DataclassSerializer):
    username: str = field(default=None)
    password: str = field(default=None)
    hostname: str = field(default='jira.service.anz')
    last_updated: str = field(default=None)
    projects: set = field(default_factory=set)

    def write_to_disk(self):
        config_dir = os.path.join(
            os.environ.get('XDG_CONFIG_HOME', os.path.join(Path.home(), '.config')), 'jira-cli'
        )
        config_filepath = os.path.join(config_dir, 'app.json')
        with open(config_filepath, 'w') as f:
            json.dump(self.serialize(), f)


def load_config(projects: set=None):
    config_dir = os.path.join(
        os.environ.get('XDG_CONFIG_HOME', os.path.join(Path.home(), '.config')), 'jira-cli'
    )
    config_filepath = os.path.join(config_dir, 'app.json')

    config = None

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
        config.username = input('Username: ')
        config.password = getpass.getpass('Password: ')

    if projects:
        # if projects is passed on the CLI, merge it into the config
        config.projects.update(projects)
        logger.info('Working with projects %s', ','.join(config.projects))

    if not config.projects:
        # abort if when there are no projects to work with!
        logger.error('No projects cached, or passed with --projects')
        sys.exit(1)

    # validate Jira connection details
    if config.username and config.password:
        try:
            Jira()._connect(config)  # pylint: disable=protected-access

            # on successful connect to JIRA API; write config to local file
            config.write_to_disk()

        except requests.exceptions.ConnectionError:
            logger.error('Failed connecting to %s', config.hostname)
            config.hostname = None

    return config

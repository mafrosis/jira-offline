from dataclasses import asdict, dataclass, field
import json
import os
import getpass
import logging
from pathlib import Path

import requests

from jira_cli.main import Jira


logger = logging.getLogger('jira')


@dataclass
class AppConfig:
    username: str = field(default=None)
    password: str = field(default=None)
    hostname: str = field(default='jira.service.anz')
    last_updated: str = field(default=None)

    def write_to_disk(self):
        config_dir = os.path.join(
            os.environ.get('XDG_CONFIG_HOME', os.path.join(Path.home(), '.config')), 'jira-cli'
        )
        config_filepath = os.path.join(config_dir, 'app.json')
        json.dump(asdict(self), open(config_filepath, 'w'))


def load_config():
    config_dir = os.path.join(
        os.environ.get('XDG_CONFIG_HOME', os.path.join(Path.home(), '.config')), 'jira-cli'
    )
    config_filepath = os.path.join(config_dir, 'app.json')

    config = None

    if os.path.exists(config_filepath):
        try:
            with open(config_filepath) as f:
                config = AppConfig(**json.load(f))
        except (IsADirectoryError, ValueError):
            pass

    if not config:
        config = AppConfig()
        config.username = input('Username: ')
        config.password = getpass.getpass('Password: ')

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

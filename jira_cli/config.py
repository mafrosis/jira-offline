import json
import os
from typing import Optional

import click

from jira_cli import __title__
from jira_cli.exceptions import UnreadableConfig
from jira_cli.models import AppConfig


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
            raise UnreadableConfig(f'There is a directory at config path (config_filepath)!')
        except ValueError:
            raise UnreadableConfig('Bad JSON in config file; ignoring')

    if not config:
        config = AppConfig()

    return config

import json
import os
from typing import Optional

import click

from jira_offline import __title__
from jira_offline.exceptions import UnreadableConfig
from jira_offline.models import AppConfig


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
            raise UnreadableConfig('There is a directory at config path (config_filepath)!')
        except ValueError:
            raise UnreadableConfig('Bad JSON in config file; ignoring')

    if not config:
        config = AppConfig()

    return config


def get_cache_filepath() -> str:
    '''
    Return the path to jira-offline issues cache file
    '''
    return os.path.join(click.get_app_dir(__title__), 'issue_cache.jsonl')

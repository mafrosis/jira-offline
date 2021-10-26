'''
Functions for reading and writing internal application config
'''
import configparser
import copy
import hashlib
import json
import logging
import os
import pathlib
from typing import Optional

import click

from jira_offline import __title__
from jira_offline.config.upgrade import upgrade_schema
from jira_offline.config.user_config import load_user_config
from jira_offline.exceptions import (DeserializeError, FailedConfigUpgrade, UnreadableConfig,
                                     UserConfigAlreadyExists)
from jira_offline.models import AppConfig, Issue, ProjectMeta
from jira_offline.utils import get_field_by_name


logger = logging.getLogger('jira')


def load_config():
    '''
    Load app configuration from local JSON file.
    '''
    config_filepath = get_app_config_filepath()

    config: Optional[AppConfig] = None

    if os.path.exists(config_filepath):
        try:
            with open(config_filepath, encoding='utf8') as f:
                config_json = json.load(f)
        except IsADirectoryError:
            raise UnreadableConfig(f'There is already a directory at {config_filepath}')
        except json.decoder.JSONDecodeError:
            raise UnreadableConfig('Bad JSON in config file!', path=config_filepath)

        upgraded_config = False

        # Upgrade configuration file if version has changed
        if config_json['schema_version'] != AppConfig().schema_version:
            upgraded_config = upgrade_schema(
                config_json, config_json['schema_version'], AppConfig().schema_version
            )

        try:
            config = AppConfig.deserialize(config_json)
        except DeserializeError as e:
            raise UnreadableConfig(e, path=config_filepath)

        # If the config schema was upgraded, persist back to disk immediately
        if upgraded_config:
            config.write_to_disk()

        # Ensure each ProjectMeta instance has a reference to the AppConfig instance
        for p in config.projects.values():
            p.config = config

    if not config:
        config = AppConfig()

    # Load settings from the user config file
    load_user_config(config)

    return config


def get_default_user_config_filepath() -> str:
    '''Return the path to jira-offline USER config file'''
    return os.path.join(
        os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config')),
        'jira-offline',
        'jira-offline.ini'
    )


def get_app_config_filepath() -> str:
    '''Return the path to jira-offline app config file'''
    return os.path.join(click.get_app_dir(__title__), 'app.json')


def get_cache_filepath() -> str:
    '''Return the path to jira-offline issues cache file'''
    return os.path.join(click.get_app_dir(__title__), 'issue_cache.feather')

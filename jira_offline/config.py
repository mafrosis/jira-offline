import json
import logging
import os
from typing import Optional

import click

from jira_offline import __title__
from jira_offline.exceptions import DeserializeError, FailedConfigUpgrade, UnreadableConfig
from jira_offline.models import AppConfig


logger = logging.getLogger('jira')


def load_config():
    '''
    Load app configuration from local JSON file
    '''
    config_filepath = get_config_filepath()

    config: Optional[AppConfig] = None

    if os.path.exists(config_filepath):
        try:
            with open(config_filepath) as f:
                config_json = json.load(f)
        except IsADirectoryError:
            raise UnreadableConfig(f'There is already a directory at {config_filepath}')
        except json.decoder.JSONDecodeError:
            raise UnreadableConfig('Bad JSON in config file!', path=config_filepath)

        # upgrade configuration file if version has changed
        if config_json['schema_version'] != AppConfig().schema_version:
            upgrade_schema(config_json, config_json['schema_version'], AppConfig().schema_version)

        try:
            config = AppConfig.deserialize(config_json)
        except DeserializeError as e:
            raise UnreadableConfig(e, path=config_filepath)

        # ensure schema is set to latest
        config.schema_version = AppConfig().schema_version

        # ensure each ProjectMeta instance has a reference to the AppConfig instance
        for p in config.projects.values():
            p.config = config

    if not config:
        config = AppConfig()

    return config


def get_config_filepath() -> str:
    '''Return the path to jira-offline config file'''
    return os.path.join(click.get_app_dir(__title__), 'app.json')


def get_cache_filepath() -> str:
    '''Return the path to jira-offline issues cache file'''
    return os.path.join(click.get_app_dir(__title__), 'issue_cache.parquet')


def upgrade_schema(config_json: dict, from_version: int, to_version: int):
    '''
    Upgrade the config file schema from one version to another
    '''
    func = globals().get(f'config_upgrade_{from_version}_to_{to_version}')
    if callable(func):
        try:
            func(config_json)
            logger.info('Upgraded app.config schema from %s to %s', from_version, to_version)
        except:
            raise FailedConfigUpgrade


def config_upgrade_1_to_2(config_json: dict):
    '''
    In version 2, new field ProjectMeta.components was added
    '''
    for project_dict in config_json['projects'].values():
        project_dict['components'] = set()

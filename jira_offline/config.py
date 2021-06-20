import configparser
import json
import logging
import os
import pathlib
from typing import Optional
import warnings

import click

from jira_offline import __title__
from jira_offline.exceptions import (DeserializeError, FailedConfigUpgrade, UnreadableConfig,
                                     UserConfigAlreadyExists)
from jira_offline.models import AppConfig


logger = logging.getLogger('jira')


def load_config():
    '''
    Load app configuration from local JSON file.
    '''
    config_filepath = get_app_config_filepath()

    config: Optional[AppConfig] = None

    if os.path.exists(config_filepath):
        try:
            with open(config_filepath) as f:
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
    _load_user_config(config)

    return config


def _load_user_config(config: AppConfig):
    '''
    Load user configuration from local INI file.

    Override fields on AppConfig with any fields set in user configuration.
    '''
    def parse_set(value: str) -> set:
        'Helper to parse comma-separated list into a set type'
        return {f.strip() for f in value.split(',')}

    if os.path.exists(config.user_config_filepath):
        cfg = configparser.ConfigParser()
        cfg.read(config.user_config_filepath)

        for section in cfg.sections():
            if section == 'display':
                if cfg[section].get('ls'):
                    config.display.ls_fields = parse_set(cfg[section]['ls'])
                if cfg[section].get('ls-verbose'):
                    config.display.ls_fields_verbose = parse_set(cfg[section]['ls-verbose'])
                if cfg[section].get('ls-default-filter'):
                    config.display.ls_default_filter = cfg[section]['ls-default-filter']
            if section == 'sync':
                if cfg[section].get('page-size'):
                    try:
                        config.sync.page_size = int(cfg[section]['page-size'])
                    except ValueError:
                        warnings.warn('Bad value in config for sync.page-size')


def write_default_user_config(config_filepath: str):
    '''
    Output a default config file to `config_filepath`
    '''
    if os.path.exists(config_filepath):
        raise UserConfigAlreadyExists(config_filepath)

    cfg = configparser.ConfigParser()

    # Write out the AppConfig default field values
    default_config = AppConfig()

    cfg.add_section('display')
    cfg['display']['ls'] = ','.join(default_config.display.ls_fields)
    cfg['display']['ls-verbose'] = ','.join(default_config.display.ls_fields_verbose)
    cfg['display']['ls-default-filter'] = default_config.display.ls_default_filter
    cfg.add_section('sync')
    cfg['sync']['page-size'] = str(default_config.sync.page_size)

    # Ensure config path exists
    pathlib.Path(config_filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(config_filepath, 'w') as f:
        cfg.write(f)


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


def upgrade_schema(config_json: dict, from_version: int, to_version: int) -> bool:
    '''
    Upgrade the config file schema from one version to another
    '''
    func = globals().get(f'config_upgrade_{from_version}_to_{to_version}')
    if callable(func):
        try:
            # Run the upgrade function
            func(config_json)
            logger.info('Upgraded app.config schema from %s to %s', from_version, to_version)
        except:
            raise FailedConfigUpgrade

    # Ensure schema is set to latest
    config_json['schema_version'] = AppConfig().schema_version
    return True


def config_upgrade_1_to_2(config_json: dict):
    '''
    In version 2, new field ProjectMeta.components was added
    '''
    for project_dict in config_json['projects'].values():
        project_dict['components'] = set()


def config_upgrade_2_to_3(config_json: dict):
    '''
    In version 3, CustomFields.estimate was renamed to CustomFields.story_points
    '''
    for project_dict in config_json['projects'].values():
        if 'estimate' in project_dict['custom_fields']:
            project_dict['custom_fields']['story_points'] = project_dict['custom_fields']['estimate']
            del project_dict['custom_fields']['estimate']

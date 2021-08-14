import configparser
import copy
import json
import logging
import os
import pathlib
from typing import Optional

import click

from jira_offline import __title__
from jira_offline.exceptions import (DeserializeError, FailedConfigUpgrade, UnreadableConfig,
                                     UserConfigAlreadyExists)
from jira_offline.models import AppConfig, Issue
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
    Override fields on AppConfig with any fields set in user configuration, validating supplied
    values.
    '''
    def parse_list(value: str) -> list:
        'Helper to parse comma-separated list into a list type'
        return [f.strip() for f in value.split(',')]

    def validate_customfield(value: str) -> bool:
        if not value.startswith('customfield_'):
            return False
        try:
            int(value.split('_')[1])
        except (ValueError, IndexError):
            return False
        return True


    def handle_display_section(items):
        for key, value in items:
            if key == 'ls':
                config.display.ls_fields = parse_list(value)
            elif key == 'ls-verbose':
                config.display.ls_fields_verbose = parse_list(value)
            elif key == 'ls-default-filter':
                config.display.ls_default_filter = value

    def handle_sync_section(items):
        for key, value in items:
            if key == 'page-size':
                try:
                    config.sync.page_size = int(value)
                except ValueError:
                    logger.warning('Config option sync.page-size must be supplied as an integer. Ignoring.')

    def handle_customfield_section(jira_host: str, items):
        for key, value in items:
            if not validate_customfield(value):
                logger.warning('Invalid customfield "%s" supplied. Ignoring.', value)
                continue

            # Handle customfields which are defined first-class on the Issue model
            for customfield_name in ('story_points', 'parent_link'):
                if key in (customfield_name, customfield_name.replace('_', '-')):
                    if not jira_host in config.customfields:
                        config.customfields[jira_host] = {}

                    config.customfields[jira_host][customfield_name] = value
                    continue

            # Replace field name dashes with underscores
            key = key.replace('-', '_')

            try:
                # Validate customfields against Issue class attributes; they cannot clash as SQL
                # filtering via --filter would not be possible
                get_field_by_name(Issue, key)

                # Customfield name is reserved keyword, warn and skip
                logger.warning('Reserved keyword "%s" cannot be used as a customfield. Ignoring.', key)
                continue

            except ValueError:
                # Customfield name is good, add to configuration
                if not jira_host in config.customfields:
                    config.customfields[jira_host] = {}

                config.customfields[jira_host][key] = value


    if os.path.exists(config.user_config_filepath):  # pylint: disable=too-many-nested-blocks
        cfg = configparser.ConfigParser(inline_comment_prefixes='#')

        with open(config.user_config_filepath) as f:
            cfg.read_string(f.read())

        for section in cfg.sections():
            if section == 'display':
                handle_display_section(cfg.items(section))

            elif section == 'sync':
                handle_sync_section(cfg.items(section))

            elif section == 'customfields':
                # Handle the generic all-Jiras customfields section
                handle_customfield_section('*', cfg.items(section))

            elif section.startswith('customfields'):
                # Handle the Jira-specific customfields section

                try:
                    jira_host = section.split(' ')[1]
                except (IndexError, ValueError):
                    # Invalid section title; skip
                    logger.warning('Customfields section header "%s" is invalid. Ignoring.', section)
                    continue

                handle_customfield_section(jira_host, cfg.items(section))


def write_default_user_config(config_filepath: str):
    '''
    Output a default config file to `config_filepath`
    '''
    if os.path.exists(config_filepath):
        raise UserConfigAlreadyExists(config_filepath)

    cfg = configparser.ConfigParser(inline_comment_prefixes='#')

    # Write out the AppConfig default field values
    default_config = AppConfig()

    cfg.add_section('display')
    cfg.set('display', '# ls', ','.join(default_config.display.ls_fields))
    cfg.set('display', '# ls-verbose', ','.join(default_config.display.ls_fields_verbose))
    cfg.set('display', '# ls-default-filter', default_config.display.ls_default_filter)

    cfg.add_section('sync')
    cfg.set('sync', '# page-size', str(default_config.sync.page_size))

    cfg.add_section('customfields')
    cfg.set('customfields', '# story-points', '')

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
    In version 3,
    - CustomFields.estimate was renamed to CustomFields.story_points
    - ProjectMeta.custom_fields was renamed to ProjectMeta.customfields
    - Mandatory "sprint" customfield was added
    - Extended dict of user-defined customfields was added
    '''
    for project_dict in config_json['projects'].values():
        if 'estimate' in project_dict['custom_fields']:
            project_dict['custom_fields']['story_points'] = project_dict['custom_fields']['estimate']
            del project_dict['custom_fields']['estimate']

        if 'custom_fields' in project_dict:
            project_dict['customfields'] = copy.deepcopy(project_dict['custom_fields'])
            del project_dict['custom_fields']

        if not 'sprint' in project_dict['customfields']:
            project_dict['customfields']['sprint'] = 'tbc'

        if not 'extended' in project_dict['customfields']:
            project_dict['customfields']['extended'] = dict()

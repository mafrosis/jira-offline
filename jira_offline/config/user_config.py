'''
Functions for reading and writng user-editable config
'''
import configparser
import logging
import os
import pathlib

from jira_offline import __title__
from jira_offline.exceptions import UserConfigAlreadyExists
from jira_offline.models import AppConfig, Issue, UserConfig
from jira_offline.utils import get_field_by_name


logger = logging.getLogger('jira')


def _parse_list(value: str) -> list:
    'Helper to parse comma-separated list into a list type'
    return [f.strip() for f in value.split(',')]


def _validate_customfield(value: str) -> bool:
    if not value.startswith('customfield_'):
        return False
    try:
        int(value.split('_')[1])
    except (ValueError, IndexError):
        return False
    return True


def load_user_config(config: AppConfig):
    '''
    Load user configuration from local INI file.
    Override fields on AppConfig with any fields set in user configuration, validating supplied
    values.
    '''
    if os.path.exists(config.user_config_filepath):  # pylint: disable=too-many-nested-blocks
        cfg = configparser.ConfigParser(inline_comment_prefixes='#')

        with open(config.user_config_filepath, encoding='utf8') as f:
            cfg.read_string(f.read())

        for section in cfg.sections():
            if section == 'display':
                handle_display_section(config.user_config, cfg.items(section))

            elif section == 'sync':
                handle_sync_section(config.user_config, cfg.items(section))

            elif section == 'customfields':
                # Handle the generic all-Jiras customfields section
                handle_customfield_section(config.user_config, '*', cfg.items(section))

            elif section.startswith('customfields'):
                # Handle the Jira-specific customfields section

                try:
                    jira_host = section.split(' ')[1]
                except (IndexError, ValueError):
                    # Invalid section title; skip
                    logger.warning('Customfields section header "%s" is invalid. Ignoring.', section)
                    continue

                handle_customfield_section(config.user_config, jira_host, cfg.items(section))


def handle_display_section(config: UserConfig, items):
    for key, value in items:
        if key == 'ls':
            config.display.ls_fields = _parse_list(value)
        elif key == 'ls-verbose':
            config.display.ls_fields_verbose = _parse_list(value)
        elif key == 'ls-default-filter':
            config.display.ls_default_filter = value

def handle_sync_section(config: UserConfig, items):
    for key, value in items:
        if key == 'page-size':
            try:
                config.sync.page_size = int(value)
            except ValueError:
                logger.warning('Config option sync.page-size must be supplied as an integer. Ignoring.')

def handle_customfield_section(config: UserConfig, jira_host: str, items):
    for key, value in items:
        if not _validate_customfield(value):
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
    cfg.set('display', '# ls', ','.join(default_config.user_config.display.ls_fields))
    cfg.set('display', '# ls-verbose', ','.join(default_config.user_config.display.ls_fields_verbose))
    cfg.set('display', '# ls-default-filter', default_config.user_config.display.ls_default_filter)

    cfg.add_section('sync')
    cfg.set('sync', '# page-size', str(default_config.user_config.sync.page_size))

    cfg.add_section('customfields')
    cfg.set('customfields', '# story-points', '')

    # Ensure config path exists
    pathlib.Path(config_filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(config_filepath, 'w', encoding='utf8') as f:
        cfg.write(f)

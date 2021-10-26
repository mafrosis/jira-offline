'''
Functions for reading and writng user-editable config
'''
import configparser
import dataclasses
import hashlib
import logging
import os
import pathlib

from jira_offline import __title__
from jira_offline.exceptions import FieldNotOnModelClass, UserConfigAlreadyExists
from jira_offline.models import AppConfig, Issue, ProjectMeta, UserConfig
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

    Params:
        config:  Global application config object, an attribute of the jira_offline.jira.Jira singleton
    '''
    GLOBAL_SECTIONS = {
        'display': handle_display_section,
        'sync': handle_sync_section,
    }
    PER_PROJECT_SECTIONS = {
        'issue': handle_issue_section,
        'customfields': handle_customfield_section,
    }

    if os.path.exists(config.user_config_filepath):  # pylint: disable=too-many-nested-blocks
        cfg = configparser.ConfigParser(inline_comment_prefixes='#')

        with open(config.user_config_filepath, encoding='utf8') as f:
            cfg.read_string(f.read())

        for section in cfg.sections():
            parts = section.split(' ')
            section_name = parts[0]

            handler_args: tuple

            if section_name in GLOBAL_SECTIONS:
                if len(parts) > 1:
                    logger.warning('Config option "%s" applies globally not per-Jira. Ignoring.', section_name)
                    continue

                # Parsed config block applies globally
                handler_args = (cfg.items(section),)

            elif section_name in PER_PROJECT_SECTIONS:
                if len(parts) > 1:
                    # Parsed config block applies to a specific Jira host or project
                    handler_args = (cfg.items(section), parts[1])
                else:
                    # Parsed config block applies to all projects
                    handler_args = (cfg.items(section), '*')

            else:
                logger.warning('Invalid section "%s" supplied in config. Ignoring.', section_name)
                continue

            func = {**GLOBAL_SECTIONS, **PER_PROJECT_SECTIONS}.get(section_name)  # type: ignore[arg-type]
            if callable(func):
                func(config.user_config, *handler_args)

    # Some user-defined config applies to specific projects
    _apply_user_config(config)


def handle_display_section(config: UserConfig, items):
    '''
    Handler for the [display] section of user config file.

    Params:
        config:  UserConfig instance attached to global jira.config
        items:   Iterable object from ConfigParser.sections()
    '''
    for key, value in items:
        if key == 'ls':
            config.display.ls_fields = _parse_list(value)
        elif key == 'ls-verbose':
            config.display.ls_fields_verbose = _parse_list(value)
        elif key == 'ls-default-filter':
            config.display.ls_default_filter = value

def handle_sync_section(config: UserConfig, items):
    '''
    Handler for the [sync] section of user config file.

    Params:
        config:  UserConfig instance attached to global jira.config
        items:   Iterable object from ConfigParser.sections()
    '''
    for key, value in items:
        if key == 'page-size':
            try:
                config.sync.page_size = int(value)
            except ValueError:
                logger.warning('Config option sync.page-size must be an integer. Ignoring.')

def handle_issue_section(config: UserConfig, items, target: str):
    '''
    Handler for the [issue] section of user config file.

    Params:
        config:  UserConfig instance attached to global jira.config
        items:   Iterable object from ConfigParser.sections()
        target:  A string mapping to a Jira hostname, or a Jira project key
    '''
    for key, value in items:
        if key == 'default-reporter':
            config.issue.default_reporter[target] = value
        elif key == 'board-id':
            config.issue.board_id[target] = value

def handle_customfield_section(config: UserConfig, items, target: str):
    '''
    Handler for the [customfield] section of user config file.

    Params:
        config:  UserConfig instance attached to global jira.config
        items:   Iterable object from ConfigParser.sections()
        target:  A string mapping to a Jira hostname, or a Jira project key
    '''
    for key, value in items:
        if not _validate_customfield(value):
            logger.warning('Invalid customfield "%s" supplied in config. Ignoring.', value)
            continue

        # Handle customfields which are defined first-class on the Issue model
        for customfield_name in ('story_points', 'parent_link'):
            if key in (customfield_name, customfield_name.replace('_', '-')):
                if not target in config.customfields:
                    config.customfields[target] = {}

                config.customfields[target][customfield_name] = value
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

        except FieldNotOnModelClass:
            # Customfield name is good, add to configuration
            if not target in config.customfields:
                config.customfields[target] = {}

            config.customfields[target][key] = value


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

    cfg.add_section('issue')
    cfg.set('issue', '# board-id', '123')
    cfg.set('issue', '# default-reporter', 'bob')

    cfg.add_section('customfields')
    cfg.set('customfields', '# story-points', '')

    # Ensure config path exists
    pathlib.Path(config_filepath).parent.mkdir(parents=True, exist_ok=True)

    with open(config_filepath, 'w', encoding='utf8') as f:
        cfg.write(f)


def _apply_user_config(config: AppConfig):
    '''
    Apply any relevant user-defined configuration to the configured projects. As some user-defined
    config is project specific (eg. default_reporter) it needs to be mapped to each project on load.

    Params:
        config:  The freshly loaded app configuration
    '''
    if not config.user_config_filepath or not os.path.exists(config.user_config_filepath):
        return

    with open(config.user_config_filepath, 'rb') as f:
        current_user_config_hash = hashlib.sha1(f.read()).hexdigest()

    if current_user_config_hash != config.user_config_hash:
        for project in config.projects.values():
            apply_user_config_to_project(config, project)


def apply_user_config_to_project(config: AppConfig, project: ProjectMeta):
    '''
    Apply user-defined configuration to the project. Some user-defined config options apply to all
    projects, or just to specific ones by hostname or project key. These must be applied at run-time
    to ensure changes are picked up and merged into the ProjectMeta objects.

    Params:
        config:   Global application config object, an attribute of the jira_offline.jira.Jira singleton
        project:  Project to apply config to
    '''
    def iter_project_user_config_fields(obj):
        '''Iterate k/v user config pairs, which are configured as applying to projects'''
        for f in dataclasses.fields(obj):
            if dataclasses.is_dataclass(f.type):
                yield from iter_project_user_config_fields(getattr(obj, f.name))
            elif f.metadata.get('project_config'):
                yield (f.name, getattr(obj, f.name))

    for field_name, field_config in iter_project_user_config_fields(config.user_config):
        # First, apply settings which apply to all projects
        if '*' in field_config:
            setattr(project, field_name, field_config['*'])

        # Second, apply per-Jira host and per-project customfield mappings to this project, in order
        for match in ('hostname', 'key'):
            for target, value in field_config.items():
                if target == getattr(project, match):
                    setattr(project, field_name, value)

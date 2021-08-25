'''
Schema upgrades for internal config
'''
import copy
import hashlib
import logging
import os

from jira_offline import __title__
from jira_offline.exceptions import FailedConfigUpgrade
from jira_offline.models import AppConfig


logger = logging.getLogger('jira')


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


def config_upgrade_3_to_4(config_json: dict):
    '''
    In version 4,
    - AppConfig.user_config_hash was added
    '''
    if config_json.get('user_config_filepath') and os.path.exists(config_json['user_config_filepath']):
        with open(config_json['user_config_filepath'], 'rb') as f:
            config_json['user_config_hash'] = hashlib.sha1(f.read()).hexdigest()

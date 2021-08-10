'''
Two util functions for converting _from_ an API response to an Issue, and for converting an Issue
_to_ an object good for an API post.
'''
import logging
from typing import Optional, Union, TYPE_CHECKING

from jira_offline.utils import get_field_by_name

if TYPE_CHECKING:
    from jira_offline.models import Issue, ProjectMeta


logger = logging.getLogger('jira')


def jiraapi_object_to_issue(project: 'ProjectMeta', issue: dict) -> 'Issue':
    '''
    Convert raw JSON from Jira API to Issue object

    Params:
        project:  Properties of the project pushing issues to
        issue:    JSON dict of an Issue from the Jira API
    Return:
        An Issue dataclass instance
    '''
    jiraapi_object = {
        'components': [x['name'] for x in issue['fields']['components']],
        'created': issue['fields']['created'],
        'description': issue['fields']['description'],
        'fix_versions': {x['name'] for x in issue['fields']['fixVersions']},
        'id': issue['id'],
        'issuetype': issue['fields']['issuetype']['name'],
        'key': issue['key'],
        'labels': issue['fields']['labels'],
        'priority': issue['fields']['priority']['name'] if issue['fields']['priority'] else '',
        'project_id': project.id,
        'status': issue['fields']['status']['name'],
        'summary': issue['fields']['summary'],
        'updated': issue['fields']['updated'],
    }

    # In an extreme edge case, Jira returned both creator and reporter as null
    for field_name in ('assignee', 'creator', 'reporter'):
        if issue['fields'].get(field_name):
            jiraapi_object[field_name] = issue['fields'][field_name]['displayName']

    # Iterate customfields configured for the current project, and extract from the API response
    if project.customfields:
        for customfield_name, customfield_ref in project.customfields.items():
            if customfield_name.startswith('extended.'):
                if 'extended' not in jiraapi_object:
                    jiraapi_object['extended'] = {}
                jiraapi_object['extended'][customfield_name[9:]] = issue['fields'].get(customfield_ref, None)
            else:
                # Late import to avoid circular dependency
                from jira_offline.models import CustomFields  # pylint: disable=import-outside-toplevel, cyclic-import

                preprocess_func = get_field_by_name(CustomFields, customfield_name).metadata.get(
                    'parse_func', preprocess_noop
                )
                jiraapi_object[customfield_name] = preprocess_func(issue['fields'].get(customfield_ref, None))

    # Late import to avoid circular dependency
    from jira_offline.models import Issue  # pylint: disable=import-outside-toplevel, cyclic-import
    return Issue.deserialize(jiraapi_object, project=project)


def issue_to_jiraapi_update(project: 'ProjectMeta', issue: 'Issue', modified: set) -> dict:
    '''
    Convert an Issue object to a JSON blob to update the Jira API. Handles both new and updated
    Issues.

    Params:
        project:   Properties of the project pushing issues to
        issue:     Issue model to create an update for
        modified:  Set of modified fields (created by a call to `sync.build_update`)
    Return:
        A JSON-compatible Python dict
    '''
    # Serialize all Issue data to be JSON-compatible
    issue_values: dict = issue.serialize()

    # Create a mapping of Issue class properties, as some fields require a different format when
    # posted to the Jira API
    field_keys: dict = {k: k for k in issue_values.keys()}

    # Pass the Jira-internal project ID
    field_keys['project_id'] = 'project'
    issue_values['project_id'] = {'id': project.jira_id}

    # Never include Issue.key, as it's invalid for create and in the URL for edit
    if 'key' in modified:
        modified.remove('key')

    # Include the customfields
    if project.customfields:
        for customfield_name, customfield_ref in project.customfields.items():
            # Include mapping from the customfield name, to the customfield identifier on Jira
            field_keys[customfield_name] = customfield_ref

            # Add a mapping of the extended customfield name to the actual value
            if customfield_name.startswith('extended.'):
                issue_values[customfield_name] = issue_values['extended'][customfield_name[9:]]

    for field_name in ('assignee', 'issuetype', 'reporter', 'priority'):
        if field_name in issue_values:
            issue_values[field_name] = {'name': issue_values[field_name]}

    # Include only modified fields
    return {
        field_keys[field_name]: issue_values[field_name]
        for field_name in modified
    }


def preprocess_noop(val: str) -> str:
    return val


def preprocess_sprint(val: Optional[Union[str, dict]]=None) -> Optional[str]:
    'Utility function to process the Jira API sprint field into a simply sprint name'
    if val is None:
        return None

    try:
        if isinstance(val[0], dict):
            return str(val[0]['name'])
        elif isinstance(val[0], str):
            return val[0][val[0].index('name=')+5:val[0].index(',', val[0].index('name='))]
        else:
            logger.debug('Failed parsing sprint name from "{val[0]}"')

    except (IndexError, KeyError):
        logger.debug('Error parsing sprint name from "{val[0]}"')

    return None

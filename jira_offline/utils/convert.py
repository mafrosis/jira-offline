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
        'creator': issue['fields']['creator']['displayName'],
        'description': issue['fields']['description'],
        'fix_versions': {x['name'] for x in issue['fields']['fixVersions']},
        'id': issue['id'],
        'issuetype': issue['fields']['issuetype']['name'],
        'key': issue['key'],
        'labels': issue['fields']['labels'],
        'priority': issue['fields']['priority']['name'] if issue['fields']['priority'] else '',
        'project_id': project.id,
        'reporter': issue['fields']['reporter']['displayName'],
        'status': issue['fields']['status']['name'],
        'summary': issue['fields']['summary'],
        'updated': issue['fields']['updated'],
    }
    if issue['fields'].get('assignee'):
        jiraapi_object['assignee'] = issue['fields']['assignee']['displayName']

    # Iterate customfields configured for the current project, and extract from the API response
    if project.customfields:
        for customfield_name, customfield_ref in project.customfields.items():
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

    # Include the customfields
    if project.customfields:
        for customfield_name, customfield_ref in project.customfields.items():
            field_keys[customfield_name] = customfield_ref

    for field_name in ('assignee', 'issuetype', 'reporter'):
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

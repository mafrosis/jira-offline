'''
Two util functions for converting _from_ an API response to an Issue, and for converting an Issue
_to_ an object good for an API post.
'''
import logging
from typing import Generator, List, Optional, Union, Set, TYPE_CHECKING

from jira_offline.exceptions import ProjectHasNoSprints, UnknownSprintError
from jira_offline.utils import get_field_by_name

if TYPE_CHECKING:
    from jira_offline.models import Issue, ProjectMeta, Sprint


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
            value = issue['fields'].get(customfield_ref, None)

            if customfield_name.startswith('extended.'):
                if 'extended' not in jiraapi_object:
                    jiraapi_object['extended'] = {}
                jiraapi_object['extended'][customfield_name[9:]] = value
            else:
                # Late import to avoid circular dependency
                from jira_offline.models import CustomFields  # pylint: disable=import-outside-toplevel, cyclic-import

                parse_func = get_field_by_name(CustomFields, customfield_name).metadata.get('parse_func')
                if value and callable(parse_func):
                    value = parse_func(value)

                jiraapi_object[customfield_name] = value

    from jira_offline.models import Issue  # pylint: disable=import-outside-toplevel, cyclic-import
    return Issue.deserialize(jiraapi_object, project)


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

    if 'sprint' in modified and issue.sprint:
        try:
            from jira_offline.models import Issue  # pylint: disable=import-outside-toplevel, cyclic-import
            original = Issue.deserialize(issue.original, issue.project)

            if not original.sprint:
                # Issue.sprint has no previous value; send the current value to the API
                issue_values['sprint'] = next(iter(issue.sprint)).id
            else:
                # Send only the diff value for the sprint field. Only a single new sprint ID is
                # accepted via the API. See the `reset_before_edit` on Issue.sprint.
                issue_values['sprint'] = next(iter(issue.sprint.difference(original.sprint))).id

        except KeyError:
            logger.info('Unrecognised sprint on %s, skipping update on this field.', issue.key)
            del issue_values['sprint']
            del field_keys['sprint']

    # Include only modified fields
    return {
        field_keys[field_name]: issue_values[field_name]
        for field_name in modified
    }


def parse_sprint(val: Union[str, dict]) -> Optional[List[dict]]:
    '''
    Utility function to process the Jira API sprint field into a list of Sprint object dicts.

    Params:
        val:  Either a string or a dict, dependent on the version of Jira server which responded
    '''
    def extract(src: str, word: str) -> str:
        'Extract value from `src`, where `word`=value'
        return src[ src.index(f'{word}=')+len(word)+1:src.index(',', src.index(f'{word}=')) ]

    def make_sprint(sprint_id: str, name: str, state: str) -> dict:
        'Return dict equivalent to Sprint.serialize()'
        return {'id': int(sprint_id), 'name': name, 'active': bool(state.lower() == 'active')}

    try:
        if isinstance(val[0], dict):
            return [make_sprint(x['id'], x['name'], x['state']) for x in val]  # type: ignore[index]
        elif isinstance(val[0], str):
            return [make_sprint(extract(x, 'id'), extract(x, 'name'), extract(x, 'state')) for x in val]
        else:
            raise KeyError

    except (IndexError, KeyError):
        logger.debug('Error parsing sprint name from "{val[0]}"')

    return None


def sprint_objects_to_names(sprints: Set['Sprint']) -> Generator[str, None, None]:
    '''
    Utility function to convert a set of sprint objects into a set of sprint names. This is used
    when rendering a set of Sprint objects in the CLI, and is mapped via dataclass.field metadata in
    the Issue model.

    Params:
        sprints:  Set of sprint objects to return as list of Sprint names
    '''
    for sprint in sorted(sprints):
        yield sprint.name


def sprint_name_to_sprint_object(project: 'ProjectMeta', sprint_name: str) -> 'Sprint':
    '''
    Utility function to return a Sprint object, when passed a sprint name.

    Params:
        project_id:   Internal project ID
        sprint_name:  Text name of a sprint
    '''
    if not project.sprints:
        raise ProjectHasNoSprints

    try:
        return next(x for x in project.sprints.values() if x.name == sprint_name)
    except StopIteration:
        raise UnknownSprintError(project.key, sprint_name)

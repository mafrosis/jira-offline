'''
Two util functions for converting _from_ an API response to an Issue, and for converting an Issue
_to_ an object good for an API post.
'''
import dataclasses
from typing import TYPE_CHECKING

from jira_offline.models import Issue

if TYPE_CHECKING:
    from jira_offline.models import ProjectMeta


def jiraapi_object_to_issue(project: 'ProjectMeta', issue: dict) -> Issue:
    '''
    Convert raw JSON from Jira API to Issue object

    Params:
        project:  Properties of the project pushing issues to
        issue:    JSON dict of an Issue from the Jira API
    Return:
        An Issue dataclass instance
    '''
    jiraapi_object = {
        'project_id': project.id,
        'created': issue['fields']['created'],
        'creator': issue['fields']['creator']['name'],
        'epic_name': issue['fields'].get(f'customfield_{project.custom_fields.epic_name}', None),
        'epic_ref': issue['fields'].get(f'customfield_{project.custom_fields.epic_ref}', None),
        'description': issue['fields']['description'],
        'fixVersions': {x['name'] for x in issue['fields']['fixVersions']},
        'id': issue['id'],
        'issuetype': issue['fields']['issuetype']['name'],
        'key': issue['key'],
        'labels': issue['fields']['labels'],
        'priority': issue['fields']['priority']['name'],
        'project': issue['fields']['project']['key'],
        'reporter': issue['fields']['reporter']['name'],
        'status': issue['fields']['status']['name'],
        'summary': issue['fields']['summary'],
        'updated': issue['fields']['updated'],
    }
    if issue['fields'].get('assignee'):
        jiraapi_object['assignee'] = issue['fields']['assignee']['name']

    # support Issue.estimate aka "Story Points", if in use
    if issue['fields'].get(f'customfield_{project.custom_fields.estimate}'):
        jiraapi_object['estimate'] = issue['fields'][f'customfield_{project.custom_fields.estimate}']

    return Issue.deserialize(jiraapi_object, project_ref=project)


def issue_to_jiraapi_update(project: 'ProjectMeta', issue: Issue, modified: set) -> dict:
    '''
    Convert an Issue object to a JSON blob to update the Jira API. Handles both new and updated
    Issues.

    Params:
        project:   Properties of the project pushing issues to
        issue:     Issue model to create an update for
        modified:  Set of modified fields (created by a call to _build_update)
    Return:
        A JSON-compatible Python dict
    '''
    # create a mapping of Issue keys (custom fields have a different key on Jira)
    field_keys: dict = {f.name: f.name for f in dataclasses.fields(Issue)}
    field_keys['epic_ref'] = f'customfield_{project.custom_fields.epic_ref}'
    field_keys['epic_name'] = f'customfield_{project.custom_fields.epic_name}'

    # support Issue.estimate aka "Story Points", if in use
    field_keys['estimate'] = f'customfield_{project.custom_fields.estimate}'

    # serialize all Issue data to be JSON-compatible
    issue_values: dict = issue.serialize()
    # some fields require a different format via the Jira API
    issue_values['project'] = {'key': issue_values['project']}

    for field_name in ('assignee', 'issuetype', 'reporter'):
        if field_name in issue_values:
            issue_values[field_name] = {'name': issue_values[field_name]}

    include_fields: set = set(modified).copy()

    # build an update dict
    return {
        field_keys[field_name]: issue_values[field_name]
        for field_name in include_fields
    }

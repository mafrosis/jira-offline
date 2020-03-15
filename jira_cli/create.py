'''
Module for functions related to Issue creation and bulk import.
'''
import logging
import uuid
from typing import Optional, TYPE_CHECKING

from jira_cli.exceptions import DeserializeError, EpicNotFound, SummaryAlreadyExists
from jira_cli.models import Issue, IssueStatus, ProjectMeta
from jira_cli.utils import get_field_by_name
from jira_cli.utils.serializer import deserialize_value

if TYPE_CHECKING:
    import Jira


logger = logging.getLogger('jira')


def get_epic_key_matching_summary_or_epic_name(jira: 'Jira', project_key: str, epic_ref: str) -> Optional[str]:
    '''
    Check if epic_ref string matches summary or epic_name on existing Epic, in project with project_key

    Params:
        jira:         Dependency-injected main.Jira object
        project_key:  Jira project key
        epic_ref:     Issue.epic_ref field
        epic_name:    Issue.epic_name field
    '''
    for issue in jira.values():
        if issue.project is None or issue.project != project_key:
            continue
        if issue.issuetype == 'Epic' and epic_ref in (issue.summary, issue.epic_name):
            return issue.key
    return None


def check_summary_exists(jira: 'Jira', project_key: str, summary: str) -> bool:
    '''
    Check if summary string already used in project with project_key

    Params:
        jira:         Dependency-injected main.Jira object
        project_key:  Jira project key
        summary:      Issue.summary field
    '''
    for issue in jira.values():
        if issue.project != project_key:
            continue
        if issue.summary == summary:
            return True
    return False


def create_issue(jira: 'Jira', project: ProjectMeta, issuetype: str, summary: str, **kwargs) -> Issue:
    '''
    Create a new Issue

    Params:
        jira:       Dependency-injected main.Jira object
        project:    Project properties on which to create the new issue
        issuetype:  Issue.issuetype
        summary:    Issue.summary
        kwargs:     Issue fields as parameters
    '''
    # ensure issues are loaded, as write_issues called on success
    if not jira:
        jira.load_issues()

    new_issue = Issue.deserialize(
        {
            'project_id': project.id,
            'project': project.key,
            'issuetype': issuetype,
            'summary': summary,
        },
        project_ref=project
    )

    # although description is an API mandatory field, we can survive without one
    if 'description' not in kwargs or not kwargs['description']:
        kwargs['description'] = ''

    # new Issues have no status (Jira project workflow settings will determine this)
    kwargs['status'] = IssueStatus.Unspecified

    for field_name, value in kwargs.items():
        set_field_on_issue(new_issue, field_name, value)

    # pylint: disable=no-member
    if check_summary_exists(jira, new_issue.project, new_issue.summary):
        raise SummaryAlreadyExists

    # map the new issue to an existing epic
    if new_issue.epic_ref:
        epic_key = get_epic_key_matching_summary_or_epic_name(jira, new_issue.project, new_issue.epic_ref)
        if not epic_key:
            raise EpicNotFound(new_issue.epic_ref)

        new_issue.epic_ref = epic_key

    # use a temporary Issue.key until Jira server creates the actual key at sync-time
    new_issue.key = str(uuid.uuid4())
    jira[new_issue.key] = new_issue
    jira.write_issues()

    return jira[new_issue.key]


def set_field_on_issue(issue: Issue, field_name: str, value: str):
    if value is None:
        return

    try:
        # convert string value to Issue field type
        value = deserialize_value(get_field_by_name(field_name).type, value)

    except DeserializeError as e:
        raise DeserializeError(f'Failed parsing {field_name} with value {value} ({e})')

    setattr(issue, field_name, value)

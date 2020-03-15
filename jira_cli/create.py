'''
Module for functions related to Issue creation and bulk import.
'''
import logging
import uuid
from typing import Optional, TYPE_CHECKING

from jira_cli.exceptions import DeserializeError, EpicNotFound, SummaryAlreadyExists
from jira_cli.models import Issue, IssueStatus, ProjectMeta

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
    kwargs['project_id'] = project.id
    kwargs['project'] = project.key
    kwargs['issuetype'] = issuetype
    kwargs['summary'] = summary

    # although description is an API mandatory field, we can survive without one
    if 'description' not in kwargs or not kwargs['description']:
        kwargs['description'] = ''

    # new Issues have no status (Jira project workflow settings will determine this)
    kwargs['status'] = IssueStatus.Unspecified

    try:
        new_issue = Issue.deserialize(
            {k:v for k,v in kwargs.items() if v is not None},
            project_ref=project
        )
    except DeserializeError as e:
        raise DeserializeError(f'Failed creating Issue from supplied values! {e}')

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

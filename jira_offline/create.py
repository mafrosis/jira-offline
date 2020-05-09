'''
Module for functions related to Issue creation and bulk import.
'''
import logging
from typing import Optional, TYPE_CHECKING
import uuid

from jira_offline.exceptions import (DeserializeError, EpicNotFound, EpicSearchStrUsedMoreThanOnce,
                                     InvalidIssueType, SummaryAlreadyExists)
from jira_offline.models import Issue, ProjectMeta
from jira_offline.utils import get_field_by_name
from jira_offline.utils.serializer import deserialize_value

if TYPE_CHECKING:
    from jira_offline.main import Jira


logger = logging.getLogger('jira')


def find_epic_by_reference(jira: 'Jira', epic_ref_string: str) -> Issue:
    '''
    Find an epic by search string.

    This will attempt find an epic based on:
        1. Issue.key
        2. Issue.summary
        3. Issue.epic_name

    Params:
        jira:             Dependency-injected main.Jira object
        epic_ref_string:  String by which to find an epic
    Returns:
        Issue for matched Epic object
    '''
    # first attempt to match issue.epic_ref to an existing epic on key
    matched_epic: Optional[Issue] = jira.get(epic_ref_string)

    if matched_epic:
        return matched_epic

    for epic in jira.values():
        # skip non-Epics
        if epic.issuetype != 'Epic':
            continue

        if epic_ref_string in (epic.summary, epic.epic_name):
            if matched_epic:
                # finding two epics that match epic_ref_string is a terminal problem, because you
                # can only link an issue to a single epic
                raise EpicSearchStrUsedMoreThanOnce

            matched_epic = epic

    if not matched_epic:
        raise EpicNotFound(epic_ref_string)

    return matched_epic


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

    # validate issuetype against the specified project
    if issuetype not in project.issuetypes:
        raise InvalidIssueType

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

    for field_name, value in kwargs.items():
        set_field_on_issue(new_issue, field_name, value)

    if check_summary_exists(jira, new_issue.project, new_issue.summary):  # pylint: disable=no-member
        raise SummaryAlreadyExists

    if new_issue.epic_ref:  # pylint: disable=no-member
        matched_epic = find_epic_by_reference(jira, new_issue.epic_ref)  # pylint: disable=no-member
        new_issue.epic_ref = matched_epic.key

    # use a temporary Issue.key until Jira server creates the actual key at sync-time
    new_issue.key = str(uuid.uuid4())
    jira[new_issue.key] = new_issue
    jira.write_issues()

    return jira[new_issue.key]


def set_field_on_issue(issue: Issue, field_name: str, value: str):
    '''
    Use DataclassSerializer.deserialize_value to convert from string to the corrent type, and then
    set the single attribute on the target Issue object.

    Params:
        issue:       Issue object being updated
        field_name:  Name of the field Issue dataclass
        value:       String representation of the value to be set
    '''
    if value is None:
        return

    try:
        # convert string value to Issue field type
        value = deserialize_value(get_field_by_name(Issue, field_name).type, value)

    except DeserializeError as e:
        raise DeserializeError(f'Failed parsing {field_name} with value {value} ({e})')

    setattr(issue, field_name, value)

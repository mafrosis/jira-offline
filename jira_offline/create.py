'''
Module for functions related to Issue creation, editing and bulk import.
'''
import logging
from typing import Optional, Tuple, TYPE_CHECKING
import uuid

from jira_offline.exceptions import (EpicNotFound, EpicSearchStrUsedMoreThanOnce, ImportFailed,
                                     InvalidIssueType, ProjectNotConfigured)
from jira_offline.models import Issue, ProjectMeta
from jira_offline.utils.serializer import get_base_type
from jira_offline.utils import deserialize_single_issue_field, find_project, get_field_by_name

if TYPE_CHECKING:
    from jira_offline.jira import Jira


logger = logging.getLogger('jira')


def find_epic_by_reference(jira: 'Jira', epic_ref_string: str) -> Issue:
    '''
    Find an epic by search string.

    This will attempt find an epic based on:
        1. Issue.key
        2. Issue.summary
        3. Issue.epic_name

    Params:
        jira:             Dependency-injected jira.Jira object
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
                # finding two epics that match epic_ref_string is an exception, as you can only link
                # an issue to a single epic
                raise EpicSearchStrUsedMoreThanOnce(epic_ref_string)

            matched_epic = epic

    if not matched_epic:
        raise EpicNotFound(epic_ref_string)

    return matched_epic


def create_issue(jira: 'Jira', project: ProjectMeta, issuetype: str, summary: str, **kwargs) -> Issue:
    '''
    Create a new Issue

    Params:
        jira:       Dependency-injected jira.Jira object
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
            'issuetype': issuetype,
            'summary': summary,
        },
        project=project,
    )

    # use a temporary Issue.key until Jira server creates the actual key at sync-time
    new_issue.key = str(uuid.uuid4())

    # set into jira dict
    jira[new_issue.key] = new_issue

    # although description is mandatory on the Jira API, the Issue can survive with an empty one
    if 'description' not in kwargs or not kwargs['description']:
        kwargs['description'] = ''

    patch_issue_from_dict(jira, new_issue, kwargs)

    # write changes to disk
    jira.write_issues()

    return new_issue


def import_issue(jira: 'Jira', attrs: dict, lineno: int=None) -> Tuple[Issue, bool]:
    '''
    Import a single issue's fields from the passed dict. The issue could be new, or this could be an
    update to an issue which already exists.

    Params:
        jira:    Dependency-injected jira.Jira object
        attrs:   Dictionary containing issue fields
        lineno:  Line number from the import file
    Returns:
        Tuple of imported Issue and flag which is true if import is new object
    '''
    if 'key' in attrs:
        # assume this object is an update to an existing Issue
        return _import_modified_issue(jira, attrs, lineno), False
    else:
        # assume this object is a new issue
        return _import_new_issue(jira, attrs, lineno), True


def _import_modified_issue(jira: 'Jira', attrs: dict, lineno: int=None) -> Issue:
    '''
    Import an UPDATED issue's fields from the passed dict.

    An update to an existing issue requires:
        project:  Jira project key
        key:      Jira issue key

    Params:
        jira:   Dependency-injected jira.Jira object
        attrs:  Dictionary containing issue fields
    '''
    try:
        # fetch existing issue by key, raising KeyError if unknown
        issue = jira[attrs['key']]

    except KeyError:
        if attrs.get('key'):
            raise ImportFailed(f'Unknown issue key {attrs["key"]}', lineno)
        raise ImportFailed('Unknown issue key', lineno)

    patch_issue_from_dict(jira, issue, attrs)
    issue.commit()

    return issue


def _import_new_issue(jira: 'Jira', attrs: dict, lineno: int=None) -> Issue:
    '''
    Import a NEW issue's fields from the passed dict.

    New issues have the required fields as in `create_issue` above:
        project:    Jira project key
        issuetype:  Jira issue issuetype
        summary:    Issue summary string

    Params:
        jira:   Dependency-injected jira.Jira object
        attrs:  Dictionary containing issue fields
    '''
    try:
        # ensure all mandatory fields are in the import dict
        for field_name in ('issuetype', 'summary', 'project'):
            if field_name not in attrs:
                raise ImportFailed(f'New issue missing field "{field_name}"')

        # extract all mandatory fields from from import attrsect
        issuetype = attrs.pop('issuetype')
        summary = attrs.pop('summary')

        # retrieve the project object
        project = find_project(jira, attrs.pop('project'))

        return create_issue(jira, project, issuetype, summary, **attrs)

    except ProjectNotConfigured:
        raise ImportFailed(f'Unknown project ref {attrs["project"]} for new issue', lineno)


def patch_issue_from_dict(jira: 'Jira', issue: Issue, attrs: dict):
    '''
    Patch attributes on an Issue from the passed dict

    Params:
        jira:   Dependency-injected jira.Jira object
        attrs:  Dictionary containing issue fields
    '''
    for field_name, value in attrs.items():
        if value is None:
            # Skip nulls in patch dict
            continue

        f = get_field_by_name(Issue, field_name)

        if f.metadata.get('readonly'):
            # Do not modify readonly fields
            continue

        if get_base_type(f.type) is str and value == '':
            # When setting an Issue attribute to empty string, map it to None
            value = None
        else:
            value = deserialize_single_issue_field(field_name, value)

        setattr(issue, field_name, value)

    # Link issue to epic if epic_ref is present
    if attrs.get('epic_ref'):
        matched_epic = find_epic_by_reference(jira, attrs['epic_ref'])
        issue.epic_ref = matched_epic.key

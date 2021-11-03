'''
Module for functions related to Issue creation, editing and bulk import.
'''
import json
import logging
from typing import cast, Hashable, IO, List, Optional, Tuple
import uuid

from tqdm import tqdm

from jira_offline.exceptions import (EpicNotFound, EpicSearchStrUsedMoreThanOnce,
                                     FieldNotOnModelClass, ImportFailed, InvalidIssueType,
                                     NoInputDuringImport, ProjectNotConfigured, UnknownSprintError)
from jira_offline.jira import jira
from jira_offline.models import Issue, ProjectMeta
from jira_offline.utils import (critical_logger, deserialize_single_issue_field, find_project,
                                get_field_by_name)
from jira_offline.utils.serializer import istype


logger = logging.getLogger('jira')


def find_epic_by_reference(epic_link_string: str) -> Issue:
    '''
    Find an epic by search string.

    This will attempt find an epic based on:
        1. Issue.key
        2. Issue.summary
        3. Issue.epic_name

    Params:
        epic_link_string:  String by which to find an epic
    Returns:
        Issue for matched Epic object
    '''
    # first attempt to match issue.epic_link to an existing epic on key
    matched_epic: Optional[Issue] = jira.get(epic_link_string)

    if matched_epic:
        return matched_epic

    for epic in jira.values():
        # skip non-Epics
        if epic.issuetype != 'Epic':
            continue

        if epic_link_string in (epic.summary, epic.epic_name):
            if matched_epic:
                # finding two epics that match epic_link_string is an exception, as you can only link
                # an issue to a single epic
                raise EpicSearchStrUsedMoreThanOnce(epic_link_string)

            matched_epic = epic

    if not matched_epic:
        raise EpicNotFound(epic_link_string)

    return matched_epic


def create_issue(project: ProjectMeta, issuetype: str, summary: str, **kwargs) -> Issue:
    '''
    Create a new Issue

    Params:
        project:    Project properties on which to create the new issue
        issuetype:  Issue.issuetype
        summary:    Issue.summary
        kwargs:     Issue fields as parameters
    '''
    # Ensure issues are loaded
    if not jira:
        jira.load_issues()

    # Validate issuetype against the specified project
    if issuetype not in project.issuetypes:
        raise InvalidIssueType

    # Create an Issue using a temporary Issue.key until Jira server creates the actual key at sync-time
    new_issue = Issue(
        project_id=project.id,
        project=project,
        issuetype=issuetype,
        summary=summary,
        key=str(uuid.uuid4()),
    )

    # Although description is mandatory on the Jira API, the Issue can survive with an empty one
    if 'description' not in kwargs or not kwargs['description']:
        kwargs['description'] = ''

    patch_issue_from_dict(new_issue, kwargs)

    return new_issue


def import_jsonlines(file: IO, verbose: bool=False) -> List[Issue]:
    '''
    Import new/modified issues from JSONlines format file.

    Params:
        file:     Open file pointer to read from
        verbose:  If False display progress bar, else print status on each import/create
    '''
    def _run(pbar=None) -> List[Issue]:
        no_input = True
        issues = []

        for i, line in enumerate(file.readlines()):
            if line:
                no_input = False

                try:
                    issue, is_new = import_issue(json.loads(line))
                    issues.append(issue)

                    if is_new:
                        logger.info('New issue created: %s', issue.summary)
                    else:
                        logger.info('Issue %s updated', issue.key)

                except json.decoder.JSONDecodeError:
                    logger.error('Failed parsing line %s', i+1)
                except UnknownSprintError as e:
                    logger.error(e)
                except ImportFailed as e:
                    logger.error('%s on line %s', e.message, i+1)
            else:
                break

            if pbar:
                # Update progress
                pbar.update(1)

        if no_input:
            raise NoInputDuringImport

        return issues

    if verbose:
        issues = _run()
    else:
        with critical_logger(logger):
            # Count number of records in the import
            total = sum(1 for line in file)
            file.seek(0)

            # Show progress bar
            with tqdm(total=total, unit=' issues') as pbar:
                issues = _run(pbar)

    return issues


def import_issue(attrs: dict) -> Tuple[Issue, bool]:
    '''
    Import a single issue's fields from the passed dict. The issue could be new, or this could be an
    update to an issue which already exists.

    Params:
        attrs:   Dictionary containing issue fields
    Returns:
        Tuple[
            The imported Issue,
            Flag indicating if the issue is new,
        ]
    '''
    if attrs.get('key'):
        # Assume this object is an update to an existing Issue
        return _import_modified_issue(attrs), False
    else:
        # Assume this object is a new issue
        return _import_new_issue(attrs), True


def _import_modified_issue(attrs: dict) -> Issue:
    '''
    Update a modified issue's fields from the passed dict.

    An update to an existing issue must have the following fields:
        project:  Jira project key
        key:      Jira issue key

    Params:
        attrs:  Dictionary containing issue fields
    '''
    try:
        # fetch existing issue by key, raising KeyError if unknown
        issue: Issue = jira[attrs['key']]

    except KeyError:
        if attrs.get('key'):
            raise ImportFailed(f'Unknown issue key {attrs["key"]}')
        raise ImportFailed('Unknown issue key')

    logger.debug('Patching %s %s', issue.issuetype, issue.key)

    patch_issue_from_dict(issue, attrs)

    return issue


def _import_new_issue(attrs: dict) -> Issue:
    '''
    Create a new issue from the fields in the passed dict.

    New issues must have the required fields as in `create_issue` above:
        project:    Jira project key
        issuetype:  Jira issue issuetype
        summary:    Issue summary string

    Params:
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

        logger.debug('Creating %s "%s"', issuetype, summary)

        return create_issue(project, issuetype, summary, **attrs)

    except ProjectNotConfigured:
        if 'project' not in attrs:
            raise ImportFailed(f'No project reference on new {issuetype} "{summary}"')
        raise ImportFailed(f'Unknown project ref {attrs["project"]} for new issue')


def patch_issue_from_dict(issue: Issue, attrs: dict):
    '''
    Patch attributes on an Issue from the passed dict

    Params:
        issue:   Issue object to patch with k:v attributes
        attrs:   Dictionary containing k:v issue attributes
    '''
    for field_name, value in attrs.items():
        if value is None:
            # Skip nulls in patch dict
            continue

        if field_name == 'epic_name' and issue.issuetype != 'Epic':
            # Epic Name field is only valid for Epics
            logger.debug('%s: Skipped field "epic_name" as it\'s only applicable to epics', issue.key)
            continue

        try:
            # Extract type from Issue dataclass field
            f = get_field_by_name(Issue, field_name)

            # Cast for mypy as get_base_type uses @functools.lru_cache
            typ = cast(Hashable, f.type)

            if f.metadata.get('readonly'):
                # Do not modify readonly fields
                continue

            # Reset before edit means a field can only be modified once until it's sync'd with Jira.
            # This setting only makes sense for sets/lists; and is primarily a hack in place for
            # Issue.sprint which is a set, but can only be updated as a single value via the API.
            if f.metadata.get('reset_before_edit'):
                original_value = deserialize_single_issue_field(field_name, issue.original.get(field_name))
                setattr(issue, field_name, original_value)

            # Fields can specify a parsing function to convert input string before updating the field value
            parse_func = f.metadata.get('parse_func')
            if parse_func:
                value = parse_func(issue.project, value)

            if istype(typ, set) and not isinstance(value, set):
                # Special case where a string is passed for a set field
                if getattr(issue, field_name) is None:
                    setattr(issue, field_name, set())
                if not isinstance(value, (set, list)):
                    value = [value]
                setattr(issue, field_name, getattr(issue, field_name) | set(value))

            elif istype(typ, list) and not isinstance(value, list):
                # Special case where a string is passed for a list field
                if getattr(issue, field_name) is None:
                    setattr(issue, field_name, [])
                getattr(issue, field_name).append(value)

            elif istype(typ, str) and value == '':
                # When setting an Issue attribute to empty string, map it to None
                setattr(issue, field_name, None)
            else:
                value = deserialize_single_issue_field(field_name, value)
                setattr(issue, field_name, value)

        except FieldNotOnModelClass:
            # FieldNotOnModelClass raised by `get_field_by_name` means this field is not a core Issue
            # attribute; and is possibly an extended customfield.
            if field_name.startswith('extended.'):
                field_name = field_name[9:]

            # Verify this is really a configured customfield before continuing
            if issue.project.customfields and issue.project.customfields.extended is not None:
                if field_name not in issue.project.customfields.extended:
                    continue

            # Dynamic user-defined customfields are stored in issue.extended dict and are always
            # str, so no type conversion is necessary.
            if not issue.extended:
                issue.extended = dict()

            issue.extended[field_name] = value

    # Link issue to epic if epic_link is present
    if attrs.get('epic_link'):
        matched_epic = find_epic_by_reference(attrs['epic_link'])
        issue.epic_link = matched_epic.key

    # Commit issue object changes back into the DataFrame
    issue.commit()

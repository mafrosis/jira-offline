'''
Module for functions related to Issue creation, editing and bulk import.
'''
import dataclasses
import functools
import json
import io
import logging
from typing import cast, Hashable, IO, List, Optional, Set, Tuple
import uuid

import pandas as pd
from tqdm import tqdm

from jira_offline.exceptions import (EpicNotFound, EpicSearchStrUsedMoreThanOnce,
                                     FieldNotOnModelClass, ImportFailed, InvalidIssueType,
                                     NoInputDuringImport, ProjectNotConfigured)
from jira_offline.jira import jira
from jira_offline.models import CustomFields, Issue, ProjectMeta
from jira_offline.utils import (critical_logger, deserialize_single_issue_field, find_project,
                                get_field_by_name)
from jira_offline.utils.serializer import DeserializeError, istype


logger = logging.getLogger('jira')


def find_linked_issue_by_ref(search_str: str) -> Issue:
    '''
    Find a linked issue by search string.

    This will attempt find a linked issue by searching in this order:
       1. Issue.key
       2. Issue.epic_name
       3. Issue.summary

    Params:
       search_str:  String to search for
    Returns:
       Matched Issue object
    '''
    # First attempt to match the search string to an existing issue key
    matched: Optional[Issue] = jira.get(search_str)
    if matched:
        return matched

    keys = list(jira.df[jira.df.epic_name == search_str].index)
    if len(keys) == 1:
        return cast(Issue, jira[keys[0]])
    if len(keys) > 0:
        raise EpicSearchStrUsedMoreThanOnce(search_str)

    keys = list(jira.df[jira.df.summary.str.match(f'(.*){search_str}(.*)')].index)
    if len(keys) == 1:
        return cast(Issue, jira[keys[0]])
    if len(keys) > 0:
        raise EpicSearchStrUsedMoreThanOnce(search_str)

    raise EpicNotFound(search_str)


def create_issue(project: ProjectMeta, issuetype: str, summary: str, strict: bool=False, **kwargs) -> Issue:
    '''
    Create a new Issue

    Params:
        project:    Project properties on which to create the new issue
        issuetype:  Issue.issuetype
        summary:    Issue.summary
        strict:     When true, raise exceptions on errors during import
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

    patch_issue_from_dict(new_issue, kwargs, strict=strict)

    return new_issue


def import_csv(file: IO, verbose: bool=False, strict: bool=False) -> List[Issue]:
    '''
    Import new/modified issues from CSV file.

    Params:
        file:     Open file pointer to read from
        verbose:  If False display progress bar, else print status on each import/create
    '''
    df = pd.read_csv(file)

    # Rename s/project_key/project
    df.rename(columns={'project_key': 'project'}, inplace=True)

    # Dump the DataFrame to JSON lines and import
    return import_jsonlines(
        io.StringIO(df.to_json(orient='records', lines=True)),
        verbose=verbose,
        strict=strict,
    )


def import_jsonlines(file: IO, verbose: bool=False, strict: bool=False) -> List[Issue]:
    '''
    Import new/modified issues from JSONlines format file.

    Params:
        file:     Open file pointer to read from
        verbose:  If False display progress bar, else print status on each import/create
        strict:   When true, raise exceptions on errors during import
    '''
    def _run(pbar=None) -> List[Issue]:
        no_input = True
        issues = []

        for i, line in enumerate(file.readlines()):
            if line:
                no_input = False

                try:
                    issue, was_created = import_issue(json.loads(line), strict=strict)
                    if issue:
                        issues.append(issue)

                        if was_created:
                            logger.info('New issue created: %s', issue.summary)
                        else:
                            logger.info('Issue updated: %s', issue.key)

                except json.decoder.JSONDecodeError:
                    logger.error('Failed parsing line %s', i+1)
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


def import_issue(attrs: dict, strict: bool=False) -> Tuple[Optional[Issue], bool]:
    '''
    Import a single issue's fields from the passed dict. The issue could be new, or this could be an
    update to an issue which already exists.

    Params:
        attrs:   Dictionary containing issue fields
        strict:  When true, raise exceptions on errors during import
    Returns:
        Tuple[
            The imported Issue object (or None if nothing was imported),
            True if the issue is new
        ]
    '''
    if attrs.get('key'):
        # Assume this object is an update to an existing Issue
        return _import_modified_issue(attrs, strict=strict), False
    else:
        # Assume this object is a new issue
        return _import_new_issue(attrs, strict=strict), True


def _import_modified_issue(attrs: dict, strict: bool=False) -> Optional[Issue]:
    '''
    Update a modified issue's fields from the passed dict.

    An update to an existing issue must have the following fields:
        project:  Jira project key
        key:      Jira issue key

    Params:
        attrs:   Dictionary containing issue fields
        strict:  When true, raise exceptions on errors during import
    '''
    try:
        # fetch existing issue by key, raising KeyError if unknown
        issue: Issue = jira[attrs['key']]

    except KeyError:
        if attrs.get('key'):
            raise ImportFailed(f'Unknown issue key {attrs["key"]}')
        raise ImportFailed('Unknown issue key')

    logger.debug('Patching %s %s', issue.issuetype, issue.key)

    if patch_issue_from_dict(issue, attrs, strict=strict):
        return issue

    return None


def _import_new_issue(attrs: dict, strict: bool=False) -> Issue:
    '''
    Create a new issue from the fields in the passed dict.

    New issues must have the required fields as in `create_issue` above:
        project:    Jira project key
        issuetype:  Jira issue issuetype
        summary:    Issue summary string

    Params:
        attrs:   Dictionary containing issue fields
        strict:  When true, raise exceptions on errors during import
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

        return create_issue(project, issuetype, summary, strict=strict, **attrs)

    except ProjectNotConfigured:
        if 'project' not in attrs:
            raise ImportFailed(f'No project reference on new {issuetype} "{summary}"')
        raise ImportFailed(f'Unknown project ref {attrs["project"]} for new issue')


@functools.lru_cache()
def get_unused_customfields(project: ProjectMeta) -> Set[str]:
    if project.customfields:
        return {
            f.name for f in dataclasses.fields(CustomFields)
            if f.name not in dict(project.customfields.items())
        }
    else:
        return set()


def patch_issue_from_dict(issue: Issue, attrs: dict, strict: bool=False) -> bool:
    '''
    Patch attributes on an Issue from the passed dict

    Params:
        issue:   Issue object to patch with k:v attributes
        attrs:   Dictionary containing k:v issue attributes
        strict:  When true, raise exceptions on error instead of just logging
    '''
    patched = False

    # Ignore unused customfields
    unused_customfields = get_unused_customfields(issue.project)

    for field_name, value in attrs.items():
        if value is None:
            # Skip nulls in patch dict
            continue

        if field_name == 'epic_name' and issue.issuetype != 'Epic':
            # Epic Name field is only valid for Epics
            logger.debug('%s: Skipped field "epic_name" as it\'s only applicable to epics', issue.key)
            continue

        if field_name in unused_customfields:
            # Ignore unused customfields
            logger.debug('%s: Skipped field "%s" as not in use on this project', issue.key, field_name)
            continue

        try:
            # Extract type from Issue dataclass field
            f = get_field_by_name(Issue, field_name)

            # Cast for mypy as get_base_type uses @functools.lru_cache
            typ = cast(Hashable, f.type)

            if f.metadata.get('readonly'):
                # Do not modify readonly fields
                logger.debug('%s: Skipped readonly field "%s"', issue.key, field_name)
                continue

            # Link an issue to epic/parent, if link field is supplied
            if field_name in ('epic_link', 'parent_link'):
                try:
                    matched = find_linked_issue_by_ref(attrs[field_name])
                    setattr(issue, field_name, matched.key)
                except EpicNotFound as e:
                    logger.debug('%s: Skipped linking to unknown epic %s', issue.key, field_name)
                    if strict:
                        raise e
                except EpicSearchStrUsedMoreThanOnce as e:
                    logger.debug('%s: %s', issue.key, e)
                    if strict:
                        raise e

                patched = True
                continue

            # Reset before edit means a field can only be modified once until it's sync'd with Jira.
            # This setting only makes sense for sets/lists; and is primarily a hack in place for
            # Issue.sprint which is a set, but can only be updated as a single value via the API.
            if f.metadata.get('reset_before_edit'):
                original_value = deserialize_single_issue_field(
                    field_name, issue.original.get(field_name), issue.project
                )
                setattr(issue, field_name, original_value)

            try:
                value = deserialize_single_issue_field(field_name, value, issue.project)

            except DeserializeError as e:
                logger.debug('%s: %s', issue.key, e)
                if strict:
                    raise e

            if istype(typ, set):
                # Special case where a string is passed for a set field
                if getattr(issue, field_name) is None:
                    setattr(issue, field_name, set())
                if not isinstance(value, (set, list)):
                    value = [value]
                setattr(issue, field_name, getattr(issue, field_name) | set(value))

            elif istype(typ, list):
                # Special case where a string is passed for a list field
                if getattr(issue, field_name) is None:
                    setattr(issue, field_name, [])
                getattr(issue, field_name).append(value)

            elif istype(typ, str) and value == '':
                # When setting an Issue attribute to empty string, map it to None
                setattr(issue, field_name, None)
            else:
                setattr(issue, field_name, value)

            patched = True

        except FieldNotOnModelClass:
            # FieldNotOnModelClass raised by `get_field_by_name` means this field is not a core Issue
            # attribute; and is possibly an extended customfield.
            if field_name.startswith('extended.'):
                field_name = field_name[9:]

            # Verify this is really a configured customfield before continuing
            if issue.project.customfields and issue.project.customfields.extended is not None:
                if field_name not in issue.project.customfields.extended:
                    logger.debug('%s: Skipped unrecognised customfield "%s"', issue.key, field_name)
                    continue

            # Dynamic user-defined customfields are stored in issue.extended dict and are always
            # str, so no type conversion is necessary.
            if not issue.extended:
                issue.extended = dict()

            issue.extended[field_name] = value
            patched = True

    # Commit issue object changes back into the DataFrame
    if patched:
        issue.commit()

    return patched

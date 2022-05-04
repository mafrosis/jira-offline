'''
Module for functions related to Issue editing.
'''
import dataclasses
import functools
import logging
from typing import cast, Hashable, Optional, Set

import click
from tabulate import tabulate

from jira_offline.exceptions import (EpicNotFound, EpicSearchStrUsedMoreThanOnce,
                                     EditorFieldParseFailed, EditorNoChanges, FieldNotOnModelClass)
from jira_offline.jira import jira
from jira_offline.models import CustomFields, Issue, ProjectMeta
from jira_offline.utils import deserialize_single_issue_field, get_field_by_name
from jira_offline.utils.cli import parse_editor_result
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
    remove = False

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

        if field_name.startswith('remove_'):
            # Special case for removing a value from a set/list type field
            field_name = field_name[7:]
            remove = True

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

                if remove is True:
                    setattr(issue, field_name, getattr(issue, field_name) ^ set(value))
                else:
                    setattr(issue, field_name, getattr(issue, field_name) | set(value))

            elif istype(typ, list):
                # Special case where a string is passed for a list field
                if getattr(issue, field_name) is None:
                    setattr(issue, field_name, [])

                if remove is True:
                    # Remove all instances of value from the list
                    setattr(issue, field_name, [x for x in getattr(issue, field_name) if x != value])
                else:
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


def edit_issue(issue: Issue, kwargs: dict, editor: bool):
    '''
    Patch the issue with fields from the CLI or editor
    '''
    if editor:
        retry = 1
        while retry <= 3:
            try:
                # Display interactively in $EDITOR
                editor_result_raw = click.edit(tabulate(issue.render()))
                if not editor_result_raw:
                    raise EditorNoChanges

                # Parse the editor output into a dict
                patch_dict = parse_editor_result(issue, editor_result_raw)
                break

            except (EditorFieldParseFailed, EditorNoChanges) as e:
                logger.error(e)

                if not click.confirm(f'Try again?  (retry {retry} of 3)'):
                    return
            finally:
                retry += 1
    else:
        # Validate epic parameters
        if issue.issuetype == 'Epic':
            if kwargs.get('epic_link'):
                click.echo('Parameter --epic-link is ignored when modifing an Epic', err=True)
                del kwargs['epic_link']
        else:
            if kwargs.get('epic_name'):
                click.echo('Parameter --epic-name is ignored for anything other than an Epic', err=True)

        # Ensure sprint field is valid for the project
        if 'sprint' in kwargs and not issue.project.sprints:
            click.echo(f'Project {issue.project.key} has no sprints, ignoring --sprint parameter', err=True)
            del kwargs['sprint']

        patch_dict = kwargs

    patch_issue_from_dict(issue, patch_dict)

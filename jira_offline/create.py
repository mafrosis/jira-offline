'''
Module for functions related to Issue creation and import.
'''
import json
import io
import logging
from typing import IO, List, Optional, Tuple
import uuid

import pandas as pd
from tqdm import tqdm

from jira_offline.edit import patch_issue_from_dict
from jira_offline.exceptions import (ImportFailed, InvalidIssueType, NoInputDuringImport,
                                     ProjectNotConfigured)
from jira_offline.jira import jira
from jira_offline.models import Issue, ProjectMeta
from jira_offline.utils import critical_logger, find_project


logger = logging.getLogger('jira')


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

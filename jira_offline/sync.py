'''
Functions related to pull & push of Issues to/from the Jira API. Also includes conflict analysis and
resolution functions.
'''
import dataclasses
from dataclasses import dataclass, field
import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Set

import click
import dictdiffer
from dictdiffer.merge import Merger
from dictdiffer.resolve import UnresolvedConflictsException
import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from jira_offline.exceptions import (EditorFieldParseFailed, FailedPullingIssues,
                                     FailedPullingProjectMeta, JiraApiError, JiraUnavailable)
from jira_offline.jira import jira
from jira_offline.create import patch_issue_from_dict
from jira_offline.models import Issue, ProjectMeta
from jira_offline.utils import critical_logger
from jira_offline.utils.api import get as api_get
from jira_offline.utils.cli import parse_editor_result, print_list
from jira_offline.utils.convert import jiraapi_object_to_issue, issue_to_jiraapi_update
from jira_offline.utils.serializer import DeserializeError


logger = logging.getLogger('jira')


class Conflict(Exception):
    pass


def pull_issues(projects: Optional[Set[str]]=None, force: bool=False, verbose: bool=False,
                no_retry: bool=False):
    '''
    Pull changed issues from upstream Jira API, and update project settings/metadata.

    Params:
        projects:  Project IDs to pull, if None then pull all configured projects
        force:     Force pull of all issues, not just those changed since project.last_updated
        verbose:   Verbose print all issues as they're pulled from the API (default: show progress bar)
        no_retry:  Do not retry a Jira server which is unavailable
    '''
    projects_to_pull: List[ProjectMeta]

    if projects is None:
        # pull all projects
        projects_to_pull = list(jira.config.projects.values())
    else:
        # Pull only the projects specified in `projects` parameter, which is a set of Jira project keys
        projects_to_pull = [
            project for project_id, project in jira.config.projects.items()
            if project.key in projects
        ]

    # Three or zero retries for an unresponsive Jira server
    if no_retry:
        retries = 1
    else:
        retries = 3

    for project in projects_to_pull:
        logger.info('Retrieving settings/metadata from %s', project.project_uri)
        retry = 1

        while retry <= retries:
            try:
                # Update project settings/metadata on every pull
                jira.get_project_meta(project)

            except JiraUnavailable as e:
                backoff = retry * retry
                logger.error('Jira %s is unavailable. Retry in %s seconds (%s/3)', project.project_uri, backoff, retry)
                time.sleep(backoff)
                continue
            except JiraApiError as e:
                raise FailedPullingProjectMeta(e)
            finally:
                retry += 1

            pull_single_project(project, force=force, verbose=verbose, page_size=jira.config.sync.page_size)
            break


def pull_single_project(project: ProjectMeta, force: bool, verbose: bool, page_size: int):
    '''
    Pull changed issues from upstream Jira API

    Params:
        project:    Properties of the Jira project to pull
        force:      Force pull of all issues, not just those changed since project.last_updated
        verbose:    Verbose print all issues as they're pulled from the API (default: show progress bar)
        page_size:  Number of issues requested in each API call to Jira
    '''
    # if the issue cache is not yet loaded, load before pull
    if not bool(jira):
        jira.load_issues()

    if force or project.last_updated is None:
        # first/forced load; cache must be empty
        last_updated = '2010-01-01 00:00'
        logger.warning('Querying %s for all issues', project.project_uri)
    else:
        last_updated = project.last_updated
        logger.warning(
            'Querying %s for issues since %s', project.project_uri, project.last_updated
        )

    jql = f'project = {project.key} AND updated > "{last_updated}"'

    def _run(jql: str, pbar=None) -> List[Issue]:
        page = 0
        total = 0
        issues = []

        while True:
            startAt = page * page_size

            params = {'jql': jql, 'startAt': startAt, 'maxResults': page_size}
            data = api_get(project, 'search', params=params)

            api_issues = data.get('issues', [])
            if len(api_issues) == 0:
                break
            page += 1
            total += len(api_issues)

            for api_issue in api_issues:
                # Build a list of Issue objects
                issues.append(jiraapi_object_to_issue(project, api_issue))

            if pbar:
                # update progress
                pbar.update(len(api_issues))
            else:
                logger.info('Page number %s', page)
                df = pd.DataFrame.from_dict(
                    {
                        issue['key']: jiraapi_object_to_issue(project, issue).serialize()
                        for issue in api_issues
                    },
                    orient='index'
                )
                print_list(df)

        return issues

    try:
        # single quick query to get total number of issues
        params: Dict[str, Any] = {'jql': jql, 'maxResults': 1, 'fields': 'key'}
        data = api_get(project, 'search', params=params)

        pbar = None

        if verbose:
            issues = _run(jql)
        else:
            # show progress bar
            with tqdm(total=data['total'], unit=' issues') as pbar:
                issues = _run(jql, pbar)

    except JiraApiError as e:
        raise FailedPullingIssues

    if not force:
        try:
            # Merge locally modified issues with changes made upstream on Jira
            for i, upstream_issue in enumerate(issues):
                if upstream_issue.key not in jira:
                    # Skip new issues
                    continue

                local_issue = jira[upstream_issue.key]

                # Check if the issue has been modified offline
                if local_issue.modified:
                    update_obj = merge_issues(local_issue, upstream_issue, is_upstream_merge=True)
                    issues[i] = update_obj.merged_issue

        except ConflictResolutionFailed as e:
            logger.critical('Failed resolving conflict on %s during pull!', e)
            return

    # include new/modified issues into local storage
    if issues:
        jira.update(issues)

    # cache the last_updated value
    project.last_updated = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    jira.config.write_to_disk()


@dataclass
class IssueUpdate:
    '''
    A class representing an update to an Issue (or a new Issue)
    '''
    merged_issue: Issue
    modified: set = field(default_factory=set)
    conflicts: dict = field(default_factory=dict)


def merge_issues(base_issue: Issue, updated_issue: Issue, is_upstream_merge: bool) -> IssueUpdate:
    '''
    Merge two issues and check for conflicts.

    A merge could be with an updated remote issue from Jira, or with between two issues which only
    exist locally.

    Params:
        base_issue:         Base Issue to which we are comparing
        updated_issue:      Incoming updated Issue (or Issue.blank)
        is_upstream_merge:  Flag to indicate if this merge is with an issue from upstream Jira server
    Returns:
        An IssueUpdate object created by build_update
    '''
    # Construct an object representing changes/conflicts
    update_obj = build_update(base_issue, updated_issue)

    if update_obj.conflicts:
        # Resolve any conflicts
        manual_conflict_resolution(update_obj)

    if is_upstream_merge and updated_issue is not None:
        # Set the original property to the latest version of this Issue incoming from upstream
        # this ensures the correct diff is written to disk
        update_obj.merged_issue.set_original(updated_issue.serialize())

    # Refresh merged Issue's diff_to_original field
    update_obj.merged_issue.diff()

    return update_obj


def build_update(base_issue: Issue, updated_issue: Optional[Issue]) -> IssueUpdate:
    '''
    Generate an object representing an Issue update.

    Params:
        base_issue:     Issue to be compared to another
        updated_issue:  Incoming Issue (or Issue.blank) to be compared to the base
    Returns:
        A dict object including the issue, a set of modified fields, and any conflicts

    There are three versions of the Issue at update time:

      base:      Base Issue, to which the updated Issue is compared
      updated:   Potentially modified Issue to compare to the base Issue
      original:  The original Issue as last-seen on the Jira server

    The updated and base Issues are compared to the original Issue and are merged into the final Issue.
    A conflict occurs when competing changes have been made on both the base and the updated Issue to
    the same field.

         Updated --- Merged
         /          /
      Original --- Base

    https://en.wikipedia.org/wiki/Merge_(version_control)#Three-way_merge

    There is an additional case, where the Issue object was created locally offline. In that case,
    Issue.blank() (or None) should be passed as the `updated_issue` parameter.

    The `dictdiffer` library is used to compare dicts of each Issue. This library generates a tuple
    showing which fields were added, changed & removed in the compared dicts.
    '''
    if updated_issue is None:
        # for new Issues created offline, the updated_issue must be set to Issue.blank
        updated_issue = Issue.blank()

    # Serialize both Issue objects to dict
    base_issue_dict: dict = base_issue.serialize()
    updated_issue_dict: dict = updated_issue.serialize()

    # fields to ignore during dictdiffer.diff
    ignore_fields = set(['diff_to_original', 'modified'])

    if updated_issue != Issue.blank():
        # ignore readonly fields when diffing new Issues
        ignore_fields.update({f.name for f in dataclasses.fields(Issue) if f.metadata.get('readonly')})

    m = Merger(base_issue.original, base_issue_dict, updated_issue_dict, actions={}, ignore=ignore_fields)

    try:
        m.run()
    except UnresolvedConflictsException:
        # Instruct the Merger to resolve every conflict by selecting the first patch.
        # The actual conflict resolution will be done in sync.manual_conflict_resolution.
        m.resolver.manual_resolve_conflicts(['f' for x in range(len(m.conflicts))])
        m.unify_patches()

    # Patch the original Issue data with merged changes from both sides
    merged_dict = dictdiffer.patch(m.unified_patches, base_issue.original)

    # Create an Issue object from the merged data
    merged_issue = Issue.deserialize(merged_dict, project=base_issue.project)

    def modified_fields(diffs):
        '''Yield each field name in the Merger patches'''
        for mode, field_name, value in diffs:
            if mode == 'add' and field_name == 'extended':
                pass
            elif mode in ('add', 'remove') and field_name == '':
                for fn, patch in value:
                    if fn == 'extended':
                        yield f'extended.{list(patch.keys())[0]}'
                    else:
                        yield fn
            elif mode == 'change':
                if isinstance(field_name, str):
                    yield field_name
                else:
                    yield field_name[0]
            else:
                yield field_name

    def conflicting_fields():
        for c in m.unresolved_conflicts:
            yield c.first_patch[1]

    def handle_extended_dot_naming(data, field_name):
        'Handle Issue customfield extended field lookups'
        if field_name.startswith('extended.'):
            return data['extended'][field_name[9:]]
        else:
            return data[field_name]

    conflict_fields = {
        field_name: {
            'original': handle_extended_dot_naming(base_issue.original, field_name),
            'updated': handle_extended_dot_naming(updated_issue_dict, field_name),
            'base': handle_extended_dot_naming(base_issue_dict, field_name),
        }
        for field_name in set(conflicting_fields())
    }

    # Mark conflicted fields
    for field_name in conflict_fields:
        if field_name.startswith('extended.'):
            merged_issue.extended[field_name[9:]] = Conflict()  # type: ignore[assignment,index]
        else:
            setattr(merged_issue, field_name, Conflict())

    # Return an object representing the diff
    return IssueUpdate(
        merged_issue=merged_issue,
        modified=set(modified_fields(m.unified_patches)),
        conflicts=conflict_fields,
    )


class ConflictResolutionFailed(Exception):
    pass


def manual_conflict_resolution(update_obj: IssueUpdate):
    '''
    Manually resolve conflicts with $EDITOR

    Params:
        update_obj:  Instance of IssueUpdate returned from build_update
    '''
    # Render issue to string, including conflict blocks
    issue_data = update_obj.merged_issue.render(update_obj.conflicts)
    editor_conflict_text = tabulate(issue_data)

    retry = 1
    while retry <= 3:
        try:
            # Display interactively in $EDITOR
            editor_result_raw = click.edit(
                '\n'.join([
                    '# Conflict(s) on Issue {}'.format(update_obj.merged_issue.key), '',
                    editor_conflict_text
                ])
            )

            # Error handling
            # - no changes in click.edit returns None
            # - empty string means abort
            # - any <<< >>> are bad news
            if not editor_result_raw:
                raise EditorFieldParseFailed
            for line in editor_result_raw:
                if line.startswith(('<<', '>>', '==')):
                    raise EditorFieldParseFailed

            # Parse the editor output into a dict
            patch_dict = parse_editor_result(
                update_obj.merged_issue, editor_result_raw, update_obj.conflicts
            )
            break

        except (EditorFieldParseFailed, DeserializeError) as e:
            logger.error(e)

            if not click.confirm(f'Try again?  (retry {retry} of 3)'):
                raise ConflictResolutionFailed(update_obj.merged_issue.key)
        finally:
            retry += 1
    else:
        # only reached if retries are exceeded
        raise ConflictResolutionFailed(update_obj.merged_issue.key)

    # Patch the issue with fields from the CLI or editor
    patch_issue_from_dict(update_obj.merged_issue, patch_dict)


def push_issues(verbose: bool=False) -> int:
    '''
    Push new/changed issues back to Jira server

    Params:
        verbose:  Verbose print all issues as they're pushed to Jira server (default is progress bar)
    '''
    def _run(issue_keys: List[str], pbar=None) -> int:
        count = 0

        for key in issue_keys:
            local_issue = jira[key]

            # skip issues which belong to unconfigured projects
            if local_issue.project_id not in jira.config.projects:
                logger.warning('Skipped issue for unconfigured project: %s', local_issue.summary)
                if pbar:
                    # update progress
                    pbar.update(1)
                continue

            # extract issue's project object into local variable
            project: ProjectMeta = jira.config.projects[local_issue.project_id]

            # retrieve the upstream issue
            remote_issue: Issue
            if local_issue.exists:
                remote_issue = jira.fetch_issue(project, local_issue.key)
            else:
                remote_issue = Issue.blank()

            # resolve any conflicts with upstream
            update_obj: IssueUpdate = merge_issues(local_issue, remote_issue, is_upstream_merge=True)

            update_dict: dict = issue_to_jiraapi_update(
                project, update_obj.merged_issue, update_obj.modified
            )

            try:
                if update_obj.merged_issue.exists:
                    jira.update_issue(project, update_obj.merged_issue, update_dict)
                    logger.info(
                        'Updated %s %s', update_obj.merged_issue.issuetype, update_obj.merged_issue.key
                    )
                else:
                    new_issue = jira.new_issue(project, update_dict, update_obj.merged_issue.key)
                    logger.info('Created new %s %s', new_issue.issuetype, new_issue.key)

                count += 1

            except JiraApiError as e:
                logger.error('Failed pushing %s with error "%s"', update_obj.merged_issue.key, e.message)

            if pbar:
                # update progress
                pbar.update(1)

        return count


    # Build up a list of issues to push in a specific order
    # 1. Push new issues; those created offline
    issues_to_push = jira.df.loc[jira.df.id == 0, 'key'].tolist()
    # 2. Push modified issues
    issues_to_push += jira.df.loc[(jira.df.id > 0) & jira.df.modified, 'key'].tolist()

    if verbose:
        total = _run(issues_to_push)
    else:
        with critical_logger(logger):
            # show progress bar
            with tqdm(total=len(issues_to_push), unit=' issues') as pbar:
                total = _run(issues_to_push, pbar)

    # write any changes to disk
    jira.write_issues()

    if total < len(issues_to_push):
        push_result_log_level = logging.ERROR
    else:
        push_result_log_level = logging.INFO

    logger.log(push_result_log_level, 'Pushed %s of %s issues', total, len(issues_to_push))
    return total

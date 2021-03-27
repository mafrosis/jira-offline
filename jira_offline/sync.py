'''
Functions related to pull & push of Issues to/from the Jira API. Also includes conflict analysis and
resolution functions.
'''
import copy
import dataclasses
from dataclasses import dataclass, field
import datetime
import logging
from typing import Any, Dict, Generator, List, Optional, Set, Tuple, TYPE_CHECKING

import click
import dictdiffer
import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from jira_offline.exceptions import (EpicNotFound, EstimateFieldUnavailable, FailedPullingIssues,
                                     FailedPullingProjectMeta, JiraApiError)
from jira_offline.models import Issue, ProjectMeta
from jira_offline.utils import critical_logger, friendly_title, get_field_by_name
from jira_offline.utils.api import get as api_get
from jira_offline.utils.cli import print_list
from jira_offline.utils.convert import jiraapi_object_to_issue, issue_to_jiraapi_update
from jira_offline.utils.serializer import DeserializeError, get_base_type, istype

if TYPE_CHECKING:
    from jira_offline.jira import Jira


logger = logging.getLogger('jira')


class Conflict(Exception):
    pass


def pull_issues(jira: 'Jira', projects: Optional[Set[str]]=None, force: bool=False, verbose: bool=False):
    '''
    Pull changed issues from upstream Jira API

    Params:
        jira:      Dependency-injected jira.Jira object
        projects:  Project IDs to pull, if None then pull all configured projects
        force:     Force pull of all issues, not just those changed since project.last_updated
        verbose:   Verbose print all issues as they're pulled from the API (default: show progress bar)
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

    for project in projects_to_pull:
        try:
            # Since the ProjectMeta defines options for how issues are created, we need to keep it
            # up-to-date. Update project meta on every pull.
            jira.get_project_meta(project)
        except JiraApiError as e:
            raise FailedPullingProjectMeta(e)

        pull_single_project(jira, project, force=force, verbose=verbose)


def pull_single_project(jira: 'Jira', project: ProjectMeta, force: bool, verbose: bool):  # pylint: disable=too-many-statements
    '''
    Pull changed issues from upstream Jira API

    Params:
        jira:     Dependency-injected jira.Jira object
        project:  Properties of the Jira project to pull
        force:    Force pull of all issues, not just those changed since project.last_updated
        verbose:  Verbose print all issues as they're pulled from the API (default: show progress bar)
    '''
    # if the issue cache is not yet loaded, load before pull
    if not bool(jira):
        jira.load_issues()

    if force or project.last_updated is None:
        # first/forced load; cache must be empty
        last_updated = '2010-01-01 00:00'
        logger.info('Querying %s for all issues', project.project_uri)
    else:
        last_updated = project.last_updated
        logger.info(
            'Querying %s for issues since %s', project.project_uri, project.last_updated
        )

    jql = f'project = {project.key} AND updated > "{last_updated}"'

    def _run(jql: str, pbar=None) -> List[Issue]:
        page = 0
        total = 0
        issues = []

        while True:
            startAt = page * 25

            params = {'jql': jql, 'startAt': startAt, 'maxResults': 25}
            data = api_get(project, 'search', params=params)

            api_issues = data.get('issues', [])
            if len(api_issues) == 0:
                break
            page += 1
            total += len(api_issues)

            for api_issue in api_issues:
                # convert from Jira object into Issue dataclass
                issue = jiraapi_object_to_issue(project, api_issue)

                if not force:
                    try:
                        # determine if local changes have been made
                        if jira[api_issue['key']].modified:
                            update_obj: IssueUpdate = merge_issues(
                                jira[api_issue['key']], issue, is_upstream_merge=True
                            )
                            issue = update_obj.merged_issue
                    except KeyError:
                        pass

                # build list of new/modified issues
                issues.append(issue)

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

    except ConflictResolutionFailed as e:
        logger.critical('Failed resolving conflict on %s during pull!', e)
        return

    # include new/modified issues into local storage
    if issues:
        jira.update(issues)

    logger.info('Retrieved %s issues', len(issues))

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
        is_upstream_merge:  Flag to indicate if the upstream issue has been updated during a sync
    Returns:
        An IssueUpdate object created by build_update
    '''
    # construct an object representing changes/conflicts
    update_obj = build_update(base_issue, updated_issue)

    if update_obj.conflicts:
        # resolve any conflicts
        update_obj.merged_issue = manual_conflict_resolution(update_obj)

    if is_upstream_merge and updated_issue is not None:
        # set the original property to the latest version of this Issue incoming from upstream
        # this ensures the correct diff is written to disk
        update_obj.merged_issue.set_original(updated_issue.serialize())

    # refresh merged Issue's diff_to_original field
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

    # serialize both Issue objects to dict
    base_issue_dict: dict = base_issue.serialize()
    updated_issue_dict: dict = updated_issue.serialize()

    def make_hashable(lst):
        '''Recursively convert lists and sets to be hashable tuples'''
        # clone `lst` arg to list type
        ret = list(range(len(lst)))
        for i, item in enumerate(lst):
            if isinstance(item, (list, set, tuple)):
                ret[i] = make_hashable(item)
            else:
                ret[i] = item
        return tuple(ret)

    # fields to ignore during dictdiffer.diff
    ignore_fields = set(['diff_to_original', 'modified'])

    if updated_issue != Issue.blank():
        # ignore readonly fields when diffing new Issues
        ignore_fields.update({f.name for f in dataclasses.fields(Issue) if f.metadata.get('readonly')})

    # generate two diffs to original Issue
    diff_original_to_base = set(make_hashable(list(dictdiffer.diff(
        base_issue.original, base_issue_dict, ignore=ignore_fields
    ))))
    diff_original_to_updated = set(make_hashable(list(dictdiffer.diff(
        base_issue.original, updated_issue_dict, ignore=ignore_fields
    ))))

    # create mapping of modified field_name to a count
    grouped_modified: Dict[str, int] = {}

    def iter_fieldnames_in_diff(diff: set) -> Generator[Tuple[str, str], None, None]:
        '''Iterate the field names in the passed diff, generated by dictdiffer'''
        for mode, field_name, value in diff:
            if mode in ('add', 'remove') and field_name == '':
                for fn, val in value:
                    yield fn, val
            else:
                yield field_name, value

    # union base and updated changes to make complete set of modified fields
    for field_name, value in iter_fieldnames_in_diff(diff_original_to_updated | diff_original_to_base):
        if not value:
            continue
        if field_name not in grouped_modified:
            grouped_modified[field_name] = 0
        grouped_modified[field_name] += 1

    # modifications with a count above 1 were made on both left and right
    conflict_fields: dict = {
        field_name: {
            'original': base_issue.original[field_name],
            'updated': updated_issue_dict[field_name],
            'base': base_issue_dict[field_name],
        }
        for field_name, count in grouped_modified.items() if count > 1
    }

    # make a copy of the base Issue
    merged_issue = copy.deepcopy(base_issue)

    # merge in modified fields from the updated Issue
    for field_name, _ in iter_fieldnames_in_diff(diff_original_to_updated):
        if grouped_modified[field_name] == 1:
            new_value = getattr(updated_issue, field_name)

            f = get_field_by_name(Issue, field_name)

            if get_base_type(f.type) is str and new_value == '':
                # When setting an Issue attribute to empty string, map it to None
                new_value = None

            setattr(merged_issue, f.name, new_value)

    # mark conflicted fields
    for field_name in grouped_modified:
        if grouped_modified[field_name] > 1:
            setattr(merged_issue, get_field_by_name(Issue, field_name).name, Conflict())

    # return object modelling this update
    return IssueUpdate(
        merged_issue=merged_issue,
        modified=set(grouped_modified.keys()),
        conflicts=conflict_fields,
    )


class ConflictResolutionFailed(Exception):
    pass

class EditorFieldParseFailed(ValueError):
    pass


def manual_conflict_resolution(update_obj: IssueUpdate) -> Issue:
    '''
    Manually resolve conflicts with $EDITOR

    Params:
        update_obj:  Instance of IssueUpdate returned from build_update
    '''
    # render issue to string, including conflict blocks
    issue_data = update_obj.merged_issue.render(update_obj.conflicts)
    editor_conflict_text = tabulate(issue_data)

    retries = 1
    while retries <= 3:
        try:
            # display interactively in $EDITOR
            editor_result_raw = click.edit(
                '\n'.join([
                    '# Conflict(s) on Issue {}'.format(update_obj.merged_issue.key), '',
                    editor_conflict_text
                ])
            )

            # error handling
            # - no changes in click.edit returns None
            # - empty string means abort
            # - any <<< >>> are bad news
            if not editor_result_raw:
                raise EditorFieldParseFailed
            for line in editor_result_raw:
                if line.startswith(('<<', '>>', '==')):
                    raise EditorFieldParseFailed

            # parse the editor output into a new Issue
            resolved_issue = parse_editor_result(update_obj, editor_result_raw)
            break

        except (EditorFieldParseFailed, DeserializeError):
            logger.error(
                'Failed parsing the return from manual conflict resolution! Retry %s/3', retries
            )
        finally:
            retries += 1
    else:
        # only reached if retries are exceeded
        raise ConflictResolutionFailed(update_obj.merged_issue.key)

    return resolved_issue


def parse_editor_result(update_obj: IssueUpdate, editor_result_raw: str) -> Issue:
    '''
    Parse the string returned from the conflict editor

    Params:
        update_obj:      Instance of IssueUpdate returned from build_update
        editor_result_raw:  Raw text returned by user from `click.edit` during interactive
                            conflict resolution
    Returns:
        Edited Issue object
    '''
    # create dict to lookup a dataclass field by its pretty formatted name
    issue_fields_by_friendly = {
        friendly_title(Issue, f.name):f for f in dataclasses.fields(Issue)
    }

    editor_result: Dict[str, List[str]] = {}

    # Process the raw input into a dict. Only conflicted fields are extracted as entries in the
    # dict, and the value is a list of lines from the raw input
    for line in editor_result_raw.splitlines():
        if not line or line.startswith('#') or line.startswith('-'*10):
            continue

        # parse a token from the current line
        parsed_token = ' '.join(line.split(' ')[0:4]).strip()

        if parsed_token in issue_fields_by_friendly:
            # next field found
            current_field = issue_fields_by_friendly[parsed_token]

        if current_field.name not in update_obj.conflicts:
            continue

        if current_field.name not in editor_result:
            editor_result[current_field.name] = []

        editor_result[current_field.name].append(line[len(parsed_token):].strip())

    summary_prefix = f'[{update_obj.merged_issue.key}]'

    def preprocess_field_value(field_name, val):
        if istype(get_field_by_name(Issue, field_name).type, set):
            return [item[1:].strip() for item in val]
        else:
            output = ''.join(val)

            if field_name == 'summary':
                # special case to strip the key prefix from the summary
                if output.startswith(summary_prefix):
                    output = output[len(summary_prefix):].strip()

            return output

    # fields need additional preprocessing before being passed to Issue.deserialize()
    editor_result = {k: preprocess_field_value(k, v) for k, v in editor_result.items()}

    # merge edit results into original Issue
    edited_issue_dict = update_obj.merged_issue.serialize()
    edited_issue_dict.update(editor_result)

    return Issue.deserialize(edited_issue_dict)


def push_issues(jira: 'Jira', verbose: bool=False):
    '''
    Push new/changed issues back to Jira server

    Params:
        jira:     Dependency-injected jira.Jira object
        verbose:  Verbose print all issues as they're pushed to Jira server (default is progress bar)
    '''
    def _run(issues: list, pbar=None) -> int:
        count = 0

        for local_issue in issues:
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

            if update_obj.merged_issue.exists:
                jira.update_issue(project, update_obj.merged_issue, update_dict)
                logger.info(
                    'Updated %s %s', update_obj.merged_issue.issuetype, update_obj.merged_issue.key
                )
                count += 1
            else:
                try:
                    new_issue = jira.new_issue(project, update_dict)
                    logger.info('Created new %s %s', new_issue.issuetype, new_issue.key)
                    count += 1
                except (EpicNotFound, EstimateFieldUnavailable) as e:
                    logger.error(e)

            if pbar:
                # update progress
                pbar.update(1)

        return count


    # Build up a list of issues to push in a specific order.
    #  1. Push existing issues with local changes first
    issues_to_push: List[Issue] = [i for i in jira.values() if i.diff_to_original and i.exists]
    #  2. Push new epics
    issues_to_push.extend(i for i in jira.values() if not i.exists and i.issuetype == 'Epic')
    #  3. Push all other new issues
    issues_to_push.extend(i for i in jira.values() if not i.exists and i.issuetype != 'Epic')

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

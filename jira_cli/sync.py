'''
Functions related to pull & push of Issues to/from the Jira API. Also includes conflict analysis and
resolution functions.
'''
import copy
import dataclasses
from dataclasses import dataclass, field
import datetime
import logging
from typing import Dict, Generator, List, Optional, Tuple, TYPE_CHECKING

import click
import dictdiffer
from jira.resources import Issue as ApiIssue
import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from jira_cli.exceptions import EpicNotFound, EstimateFieldUnavailable
from jira_cli.models import Issue
from jira_cli.utils import critical_logger, DeserializeError, friendly_title, is_optional_type

if TYPE_CHECKING:
    import Jira


CUSTOM_FIELD_EPIC_LINK = 'customfield_14182'
CUSTOM_FIELD_EPIC_NAME = 'customfield_14183'
CUSTOM_FIELD_ESTIMATE = 'customfield_10002'


logger = logging.getLogger('jira')


class Conflict(Exception):
    pass


def pull_issues(jira: 'Jira', projects: set=None, force: bool=False, verbose: bool=False):  # pylint: disable=too-many-statements
    '''
    Pull changed issues from upstream Jira API

    Params:
        jira:      Dependency-injected main.Jira object
        projects:  Project keys to pull, if None then pull all configured projects
        force:     Force reload of *all* issues, not just changed since `last_updated` value
        verbose:   Verbose print all issues as they're pulled from the API (default is progress bar)
    '''
    if projects is None:
        projects = jira.config.projects.keys()

    if not projects:
        raise Exception('No projects configured, cannot continue')

    for project_key in projects:
        if project_key not in jira.config.projects:
            jira.config.projects[project_key] = jira.get_project_meta(project_key)

    if force or jira.config.last_updated is None:
        # first/forced load; cache must be empty
        last_updated = '2010-01-01 00:00'
        logger.info('Querying for all Jira issues')
    else:
        if not jira:
            # load existing issue data from cache
            jira.load_issues()

        last_updated = jira.config.last_updated
        logger.info('Querying for Jira issues since %s', last_updated)

    jql = f'project IN ({",".join(projects)}) AND updated > "{last_updated}"'

    # single quick query to get total number of issues
    api = jira.connect()
    head = api.search_issues(jql, maxResults=1)

    pbar = None

    def _run(jql: str, pbar=None) -> int:
        page = 0
        total = 0

        while True:
            start = page * 25
            issues = api.search_issues(jql, start, 25)
            if len(issues) == 0:
                break
            page += 1
            total += len(issues)

            for api_issue in issues:
                # convert from Jira object into Issue dataclass
                issue = jiraapi_object_to_issue(api_issue)

                try:
                    # determine if local changes have been made
                    if jira[api_issue.key].diff_to_original:
                        # when pulling, the remote Issue is considered the base
                        update_object: IssueUpdate = check_resolve_conflicts(jira[api_issue.key], issue)
                        issue = update_object.merged_issue
                except KeyError:
                    pass

                # insert issue into Jira dict
                jira[api_issue.key] = issue

            if pbar:
                # update progress
                pbar.update(len(issues))
            else:
                logger.info('Page number %s', page)
                df = pd.DataFrame.from_dict(
                    {issue.key:jiraapi_object_to_issue(issue).serialize() for issue in issues},
                    orient='index'
                )
                df['summary'] = df.loc[:]['summary'].str.slice(0, 100)
                print(tabulate(df[['issuetype', 'summary', 'assignee', 'updated']], headers='keys', tablefmt='psql'))

        return total

    try:
        if verbose:
            total = _run(jql)
        else:
            # show progress bar
            with tqdm(total=head.total, unit=' issues') as pbar:
                total = _run(jql, pbar)

    except ConflictResolutionFailed as e:
        logger.critical('Failed resolving conflict on %s during pull!', e)
        return

    logger.info('Retrieved %s issues', total)

    # dump issues to JSON cache
    jira.write_issues()

    # cache the last_updated value
    jira.config.last_updated = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    jira.config.write_to_disk()


def jiraapi_object_to_issue(issue: ApiIssue) -> Issue:
    '''
    Convert raw JSON from Jira API to Issue object

    Params:
        issue:  Instance of the Issue class from the Jira library
    Return:
        An Issue dataclass instance
    '''
    fixVersions = set()
    if issue.fields.fixVersions:
        fixVersions = {f.name for f in issue.fields.fixVersions}

    jiraapi_object = {
        'created': issue.fields.created,
        'creator': issue.fields.creator.name,
        'epic_name': getattr(issue.fields, CUSTOM_FIELD_EPIC_NAME, ''),
        'description': issue.fields.description,
        'fixVersions': fixVersions,
        'id': issue.id,
        'issuetype': issue.fields.issuetype.name,
        'key': issue.key,
        'priority': issue.fields.priority.name,
        'project': issue.fields.project.key,
        'reporter': issue.fields.reporter.name,
        'status': issue.fields.status.name,
        'summary': issue.fields.summary,
        'updated': issue.fields.updated,
    }
    if issue.fields.assignee:
        jiraapi_object['assignee'] = issue.fields.assignee.name
    if getattr(issue.fields, CUSTOM_FIELD_EPIC_LINK):
        jiraapi_object['epic_ref'] = getattr(issue.fields, CUSTOM_FIELD_EPIC_LINK)
    if getattr(issue.fields, CUSTOM_FIELD_ESTIMATE):
        jiraapi_object['estimate'] = getattr(issue.fields, CUSTOM_FIELD_ESTIMATE)
    if issue.fields.labels:
        jiraapi_object['labels'] = issue.fields.labels

    return Issue.deserialize(jiraapi_object)


@dataclass
class IssueUpdate:
    '''
    A class representing an update to an Issue (or a new Issue)
    '''
    merged_issue: Issue
    modified: set = field(default_factory=set)
    conflicts: dict = field(default_factory=dict)


def issue_to_jiraapi_update(issue: Issue, modified: set) -> dict:
    '''
    Convert an Issue object to a JSON blob to update the Jira API. Handles both new and updated
    Issues.

    Params:
        issue:     Issue model to create an update for
        modified:  Set of modified fields (created by a call to _build_update)
    Return:
        A JSON-compatible Python dict
    '''
    # create a mapping of Issue keys (custom fields have a different key on Jira)
    field_keys: dict = {f.name: f.name for f in dataclasses.fields(Issue)}
    field_keys['epic_ref'] = CUSTOM_FIELD_EPIC_LINK
    field_keys['epic_name'] = CUSTOM_FIELD_EPIC_NAME
    field_keys['estimate'] = CUSTOM_FIELD_ESTIMATE

    # serialize all Issue data to be JSON-compatible
    issue_values: dict = issue.serialize()
    # some fields require a different format via the Jira API
    issue_values['project'] = {'key': issue_values['project']}

    for field_name in ('assignee', 'issuetype', 'reporter'):
        if field_name in issue_values:
            issue_values[field_name] = {'name': issue_values[field_name]}

    include_fields: set = set(modified).copy()

    # currently the priority field is unhandled
    if 'priority' in include_fields:
        include_fields.remove('priority')

    # don't send estimate field for Epics
    if issue_values['issuetype'] == 'Epic':
        include_fields.remove('estimate')

    # build an update dict
    return {
        field_keys[field_name]: issue_values[field_name]
        for field_name in include_fields
    }


def check_resolve_conflicts(base_issue: Issue, updated_issue: Optional[Issue]=None) -> IssueUpdate:
    '''
    Check for and resolve conflicts on a single Issue.

    Params:
        base_issue:     Base Issue to which we are comparing (has an .original property)
        updated_issue:  Incoming updated Issue - can be None for new (created offline) issues
    Returns:
        An IssueUpdate object created by _build_update
    '''
    if not bool(base_issue.id) and updated_issue is not None:
        raise Exception

    # construct an object representing changes/conflicts
    update_object = _build_update(base_issue, updated_issue)

    if update_object.conflicts:
        resolved_issue = manual_conflict_resolution(update_object)
    else:
        resolved_issue = update_object.merged_issue

    if updated_issue:
        # set the original property to the latest updated version incoming from upstream
        resolved_issue.original = updated_issue.serialize()

    # refresh merged Issue's diff_to_original field
    resolved_issue.diff_to_original = update_object.merged_issue.diff()

    # refresh resolved Issue's diff_to_original field
    update_object.merged_issue = resolved_issue
    return update_object


def _build_update(base_issue: Issue, updated_issue: Optional[Issue]) -> IssueUpdate:
    '''
    Generate an object representing an Issue update.

    There are three versions of the Issue at update time:

      original:  The original Issue before any local modifications
      base:      A modified Issue, to which the updated Issue is compared
      updated:   Incoming modified Issue

    The updated and base Issues are compared to the original Issue and are merged into the final Issue.
    A conflict occurs when competing changes have been made on both the base and the updated Issue to
    the same field.

         Updated --- Merged
         /          /
      Origin --- Base

    https://en.wikipedia.org/wiki/Merge_(version_control)#Three-way_merge

    There is an additional case, where the Issue object was created locally offline. In that case,
    None MUST be passed as the `updated_issue` parameter.

    Params:
        base_issue:     Base Issue to which we are comparing (has an .original property)
        updated_issue:  Incoming updated Issue
    Returns:
        A dict object including the issue, a set of modified fields, and any conflicts
    '''
    if updated_issue is None:
        # for new Issues created offline, the updated_issue must be set to Issue.blank
        updated_issue = Issue.blank

    # serialize both Issue objects to dict
    base_issue_dict: dict = base_issue.serialize()
    updated_issue_dict: dict = updated_issue.serialize()

    def make_hashable(lst):
        '''
        Recursively convert lists and sets to be hashable tuples
        '''
        # clone `lst` arg to list type
        ret = list(range(len(lst)))
        for i, item in enumerate(lst):
            if isinstance(item, (list, set, tuple)):
                ret[i] = make_hashable(item)
            else:
                ret[i] = item
        return tuple(ret)

    # fields to ignore during dictdiffer.diff
    ignore_fields = set(['diff_to_original'])

    if updated_issue != Issue.blank:
        # ignore readonly fields when diffing new Issues
        ignore_fields.update({f.name for f in dataclasses.fields(Issue) if f.metadata.get('readonly')})

    # generate two diffs to original Issue
    diff_original_to_base: set = set(make_hashable(list(dictdiffer.diff(
        base_issue.original, base_issue_dict, ignore=ignore_fields
    ))))
    diff_original_to_updated: set = set(make_hashable(list(dictdiffer.diff(
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
            value = getattr(updated_issue, field_name)
            if bool(value):
                setattr(merged_issue, field_name, value)

    # mark conflicted fields
    for field_name in grouped_modified:
        if grouped_modified[field_name] > 1:
            setattr(merged_issue, field_name, Conflict())

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


def manual_conflict_resolution(update_object: IssueUpdate) -> Issue:
    '''
    Manually resolve conflicts with $EDITOR

    Params:
        update_object:  Instance of IssueUpdate returned from _build_update
    '''
    # render issue to string, including conflict blocks
    editor_conflict_text = update_object.merged_issue.__str__(update_object.conflicts)

    retries = 1
    while retries <= 3:
        try:
            # display interactively in $EDITOR
            editor_result_raw = click.edit(
                '\n'.join([
                    '# Conflict(s) on Issue {}'.format(update_object.merged_issue.key), '',
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
            resolved_issue = parse_editor_result(update_object, editor_result_raw)
            break

        except (EditorFieldParseFailed, DeserializeError):
            logger.error(
                'Failed parsing the return from manual conflict resolution! Retry %s/3', retries
            )
        finally:
            retries += 1
    else:
        # only reached if retries are exceeded
        raise ConflictResolutionFailed(update_object.merged_issue.key)

    return resolved_issue


def parse_editor_result(update_object: IssueUpdate, editor_result_raw: str) -> Issue:
    '''
    Parse the string returned from the conflict editor

    Params:
        update_object:      Instance of IssueUpdate returned from _build_update
        editor_result_raw:  Raw text returned by user from `click.edit` during interactive
                            conflict resolution
    Returns:
        Edited Issue object
    '''
    # dict of Issue dataclass fields
    issue_fields = {f.name:f for f in dataclasses.fields(Issue)}

    # create dict to lookup a dataclass field by its pretty formatted name
    issue_fields_by_friendly = {
        friendly_title(f.name):f for f in dataclasses.fields(Issue)
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

        if current_field.name not in update_object.conflicts:
            continue

        if current_field.name not in editor_result:
            editor_result[current_field.name] = []

        editor_result[current_field.name].append(line[len(parsed_token):].strip())

    def preprocess_field_value(field_name, val):
        if is_optional_type(issue_fields[field_name].type, set):
            return [item[1:].strip() for item in val]
        else:
            return ''.join(val)

    # fields need additional preprocessing before being passed to Issue.deserialize()
    editor_result = {k: preprocess_field_value(k, v) for k, v in editor_result.items()}

    # merge edit results into original Issue
    edited_issue_dict = update_object.merged_issue.serialize()
    edited_issue_dict.update(editor_result)

    return Issue.deserialize(edited_issue_dict)


def push_issues(jira: 'Jira', verbose: bool=False):
    '''
    Push new/changed issues back to Jira server

    Params:
        jira:     Dependency-injected main.Jira object
        verbose:  Verbose print all issues as they're pushed to Jira server (default is progress bar)
    '''
    def _run(issues: list, pbar=None) -> int:
        count = 0

        for local_issue in issues:
            # retrieve the upstream issue
            remote_issue = _fetch_single_issue(jira, local_issue)

            # resolve any conflicts with upstream
            update_object: IssueUpdate = check_resolve_conflicts(local_issue, remote_issue)

            update_dict: dict = issue_to_jiraapi_update(
                update_object.merged_issue, update_object.modified
            )

            if update_object.merged_issue.id:
                jira.update_issue(update_object.merged_issue.key, update_dict)
                logger.info('Updated issue %s', update_object.merged_issue.key)
                count += 1
            else:
                try:
                    new_issue = jira.new_issue(update_dict)
                    logger.info('New issue %s created', new_issue.key)
                    count += 1
                except (EpicNotFound, EstimateFieldUnavailable) as e:
                    logger.error(e)

            if pbar:
                # update progress
                pbar.update(1)

        return count


    # Build up a list of issues to push in a specific order.
    #  1. Push existing issues with local changes first
    issues_to_push: List[Issue] = [i for i in jira.values() if i.diff_to_original and i.id]
    #  2. Push new epics (new items have no Issue.id)
    issues_to_push.extend(i for i in jira.values() if not i.id and i.status == 'Epic')
    #  3. Push all other new issues
    issues_to_push.extend(i for i in jira.values() if not i.id and i.status != 'Epic')

    if verbose:
        total = _run(issues_to_push)
    else:
        with critical_logger(logger):
            # show progress bar
            with tqdm(total=len(issues_to_push), unit=' issues') as pbar:
                total = _run(issues_to_push, pbar)

    # write any changes to disk
    jira.write_issues()

    logger.info('Pushed %s of %s issues', total, len(issues_to_push))


def _fetch_single_issue(jira: 'Jira', issue: Issue) -> Optional[Issue]:
    '''
    Return a single Issue object from the Jira API by key

    Params:
        jira:   Dependency-injected main.Jira object
        issue:  Local Issue to lookup on Jira API
    Returns:
        Issue dataclass instance
    '''
    # new issues will have an absent id attrib
    if not bool(issue.id):
        return None
    return jiraapi_object_to_issue(jira.connect().issue(issue.key))

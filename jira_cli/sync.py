import copy
import dataclasses
from dataclasses import dataclass, field
import datetime
import logging

import click
import dictdiffer
import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from jira_cli.models import Issue
from jira_cli.utils import DeserializeError, friendly_title


CUSTOM_FIELD_EPIC_LINK = 'customfield_14182'
CUSTOM_FIELD_EPIC_NAME = 'customfield_14183'
CUSTOM_FIELD_ESTIMATE = 'customfield_10002'


logger = logging.getLogger('jira')


class Conflict(Exception):
    pass


def pull_issues(jira: 'Jira', force: bool=False, verbose: bool=False):
    '''
    Pull changed issues from upstream Jira API

    Params:
        jira:     Dependency-injected main.Jira object
        force:    Force reload of *all* issues, not just changed since `last_updated` value
        verbose:  Verbose print all issues as they're pulled from the API (default is progress bar)
    '''
    if not jira.config.projects:
        raise Exception('No projects configured, cannot continue')

    if force or jira.config.last_updated is None:
        # first/forced load; cache must be empty
        last_updated = '2010-01-01 00:00'
        logger.info('Querying for all Jira issues')
    else:
        # load existing issue data from cache
        jira.load_issues()
        last_updated = jira.config.last_updated
        logger.info('Querying for Jira issues since %s', last_updated)

    jql = f'project IN ({",".join(jira.config.projects)}) AND updated > "{last_updated}"'

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
                issue = _raw_issue_to_object(api_issue)

                try:
                    # determine if local changes have been made
                    if jira[api_issue.key].diff_to_original:
                        # when pulling, the remote Issue is considered the base
                        issue = check_resolve_conflicts(issue, jira[api_issue.key])
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
                    {issue.key:_raw_issue_to_object(issue).serialize() for issue in issues},
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


def _raw_issue_to_object(issue: dict) -> Issue:
    '''
    Convert raw JSON from JIRA API to a dataclass object
    '''
    fixVersions = set()
    if issue.fields.fixVersions:
        fixVersions = {f.name for f in issue.fields.fixVersions}

    return Issue.deserialize({
        'assignee': issue.fields.assignee.name if issue.fields.assignee else None,
        'created': issue.fields.created,
        'creator': issue.fields.creator.name,
        'epic_ref': getattr(issue.fields, CUSTOM_FIELD_EPIC_LINK),
        'epic_name': getattr(issue.fields, CUSTOM_FIELD_EPIC_NAME, ''),
        'estimate': getattr(issue.fields, CUSTOM_FIELD_ESTIMATE),
        'description': issue.fields.description,
        'fixVersions': fixVersions,
        'issuetype': issue.fields.issuetype.name,
        'key': issue.key,
        'labels': issue.fields.labels,
        'priority': issue.fields.priority.name,
        'project': issue.fields.project.key,
        'reporter': issue.fields.reporter.name,
        'status': issue.fields.status.name,
        'summary': issue.fields.summary,
        'updated': issue.fields.updated,
    })


@dataclass
class IssueUpdate:
    '''
    A class representing an update to an Issue (or a new Issue)
    '''
    merged_issue: Issue
    modified: set = field(default_factory=set)
    conflicts: dict = field(default_factory=dict)


def check_resolve_conflicts(base_issue: Issue, updated_issue: Issue) -> Issue:
    '''
    Check for and resolve conflicts on a single Issue

    Params:
        base_issue:     Base Issue to which we are comparing (has an .original property)
        updated_issue:  Incoming updated Issue
    Returns:
        Resolved issue
    '''
    # construct an object representing changes/conflicts
    update_object = _build_update(base_issue, updated_issue)

    if not update_object.conflicts:
        return update_object.merged_issue

    return manual_conflict_resolution(update_object)


def _build_update(base_issue: Issue, updated_issue: Issue) -> IssueUpdate:
    '''
    Generate an object representing an Issue update

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

    Params:
        base_issue:     Base Issue to which we are comparing (has an .original property)
        updated_issue:  Incoming updated Issue
    Returns:
        A dict object including the issue, a set of modified fields, and any conflicts
    '''
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

    # generate two diffs to original Issue
    diff_original_to_base: set = set(make_hashable(list(dictdiffer.diff(
        base_issue.original, base_issue_dict, ignore=set(['diff_to_original'])
    ))))
    diff_original_to_updated: set = set(make_hashable(list(dictdiffer.diff(
        base_issue.original, updated_issue_dict, ignore=set(['diff_to_original'])
    ))))

    # create mapping of modified field_name to a count
    grouped_modified = {}

    # union base and updated changes to make complete set
    for _, field_name, value in diff_original_to_updated | diff_original_to_base:
        if not value:
            return
        if field_name not in grouped_modified:
            grouped_modified[field_name] = 0
        grouped_modified[field_name] += 1

    # modifications with a count above 1 were made on both base and updated
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
    for _, field_name, _ in diff_original_to_updated:
        if grouped_modified[field_name] == 1:
            setattr(merged_issue, field_name, getattr(updated_issue, field_name))

    # mark conflicted fields
    for field_name in grouped_modified:
        if grouped_modified[field_name] > 1:
            setattr(merged_issue, field_name, Conflict())

    # return object modelling this update
    return IssueUpdate(
        merged_issue=merged_issue,
        modified=grouped_modified.keys(),
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

    editor_result = {}

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
        if issue_fields[field_name].type is set:
            return [item[1:].strip() for item in val]
        else:
            return ''.join(val)

    # fields need additional preprocessing before being passed to Issue.deserialize()
    editor_result = {k: preprocess_field_value(k, v) for k, v in editor_result.items()}

    # merge edit results into original Issue
    edited_issue_dict = update_object.merged_issue.serialize()
    edited_issue_dict.update(editor_result)

    return Issue.deserialize(edited_issue_dict)

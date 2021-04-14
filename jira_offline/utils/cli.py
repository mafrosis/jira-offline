'''
Print and text rendering utils for the CLI commands
'''
import arrow
import click
import dataclasses
import pandas as pd
from tabulate import tabulate
from typing import Optional, Dict, List

from jira_offline.models import Issue
from jira_offline.utils import friendly_title, get_field_by_name
from jira_offline.utils.serializer import istype


def print_list(df: pd.DataFrame, width: int=60, verbose: bool=False, include_project_col: bool=False):
    '''
    Helper to print abbreviated list of issues

    Params:
        df:                   Issues to display in a DataFrame
        width:                Crop width for the summary string
        verbose:              Display more information
        include_project_col:  Include the Issue.project field in a column
    '''
    # intentionally make a copy of the DataFrame, so subsequent destructive changes can be made
    df = df.copy()

    if include_project_col:
        fields = ['project_key']
    else:
        fields = []

    if not verbose:
        fields += ['issuetype', 'epic_ref', 'summary', 'assignee', 'updated']
    else:
        fields += [
            'issuetype', 'epic_ref', 'epic_name', 'summary', 'assignee', 'fix_versions', 'updated'
        ]
        width = 200

    def format_datetime(raw):
        if not raw or pd.isnull(raw):
            return ''
        dt = arrow.get(raw)
        if verbose:
            return f'{dt.format()}'
        else:
            return f'{dt.humanize()}'

    # pretty dates
    df['updated'] = df.updated.apply(format_datetime)

    # shorten the summary field for printing
    df['summary'] = df.summary.str.slice(0, width)

    def abbrev_key(key):
        if key is None:
            return ''
        if len(key) == 36:
            return key[0:8]
        return key

    # abbreviate long issue keys (offline-created issues have a UUID as the key)
    df['key'] = df.key.apply(abbrev_key)
    df['epic_ref'] = df.epic_ref.apply(abbrev_key)

    if verbose:
        df.fix_versions = df.fix_versions.apply(lambda x: '' if not x else ','.join(x))

    print_table(df[fields])


def print_table(df: pd.DataFrame):
    '''Helper to pretty print dataframes'''
    click.echo(tabulate(df, headers='keys', tablefmt='psql'))


def print_diff(issue: Issue):
    if not issue.exists:
        # this issue was locally created offline so no diff is available; just do a plain print
        click.echo(issue)
        return

    # late import to avoid cyclic import
    from jira_offline.sync import build_update  # pylint: disable=import-outside-toplevel, cyclic-import

    # run build_update to diff between the remote version of the Issue, and the locally modified one
    update_obj = build_update(Issue.deserialize(issue.original), issue)

    # print a handsome table
    click.echo(tabulate(issue.render(modified_fields=update_obj.modified)))


def parse_editor_result(issue: Issue, editor_result_raw: str, conflicts: Optional[dict]=None) -> Issue:
    '''
    Parse the string returned from the conflict editor

    Params:
        issue:              Instance of issue which is being rendered in the editor
        editor_result_raw:  Raw text returned by user from `click.edit` during interactive conflict
                            resolution
    Returns:
        Edited Issue object
    '''
    # Create dict to lookup a dataclass field by its pretty formatted name
    issue_fields_by_friendly = {
        friendly_title(Issue, f.name):f for f in dataclasses.fields(Issue)
    }

    editor_result: Dict[str, List[str]] = {}

    # Process the raw input into a dict. Only conflicted fields are extracted as entries in the
    # dict, and the value is a list of lines from the raw input
    for line in editor_result_raw.splitlines():
        if not line or line.startswith('#') or line.startswith('-'*10):
            continue

        # Parse a token from the current line
        parsed_token = ' '.join(line.split(' ')[0:4]).strip()

        if parsed_token in issue_fields_by_friendly:
            # Next field found
            current_field = issue_fields_by_friendly[parsed_token]

        # If processing conflicts in the editor, ignore any fields which aren't in conflict
        if conflicts and current_field.name not in conflicts:
            continue

        if current_field.name not in editor_result:
            editor_result[current_field.name] = []

        editor_result[current_field.name].append(line[len(parsed_token):].strip())

    summary_prefix = f'[{issue.key}]'

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

    # Fields need additional preprocessing before being passed to Issue.deserialize()
    editor_result = {k: preprocess_field_value(k, v) for k, v in editor_result.items()}

    # Merge edit results into original Issue
    edited_issue_dict = issue.serialize()
    edited_issue_dict.update(editor_result)

    return Issue.deserialize(edited_issue_dict)

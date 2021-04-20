'''
Print and text rendering utils for the CLI commands
'''
import dataclasses
import decimal
import logging
from typing import Any, Dict, List, Optional

import arrow
import click
import pandas as pd
from tabulate import tabulate
import typing_inspect

from jira_offline.exceptions import EditorRepeatFieldFound
from jira_offline.models import Issue
from jira_offline.utils import friendly_title
from jira_offline.utils.serializer import istype


logger = logging.getLogger('jira')


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


def parse_editor_result(issue: Issue, editor_result_raw: str, conflicts: Optional[dict]=None) -> dict:
    '''
    Parse the string returned from the conflict editor

    Params:
        issue:              Instance of issue which is being rendered in the editor
        editor_result_raw:  Raw text returned by user from `click.edit` during interactive conflict
                            resolution
    Returns:
        Edited Issue object
    '''
    class SkipEditorField:
        pass

    # Create dict to lookup a dataclass field by its pretty formatted name
    issue_fields_by_friendly = {
        friendly_title(Issue, f.name):f for f in dataclasses.fields(Issue)
    }

    editor_result: Dict[str, List[str]] = {}

    def preprocess_field(field: dataclasses.Field, input_data: List[str]) -> Any:
        # Validate empty
        if input_data in ('', ['']):
            if not typing_inspect.is_optional_type(field.type):
                # Field is mandatory, and editor returned blank - skip this field
                return SkipEditorField()
            elif field.default_factory != dataclasses.MISSING:  # type: ignore[misc] # https://github.com/python/mypy/issues/6910
                return field.default_factory()  # type: ignore[misc]
            else:
                return field.default

        if istype(field.type, set):
            return {item[1:].strip() for item in input_data if len(item[1:].strip()) > 0}

        if istype(field.type, list):
            return [item[1:].strip() for item in input_data if len(item[1:].strip()) > 0]

        if istype(field.type, (int, decimal.Decimal)):
            # Handle number types
            field_value = input_data[0]
        else:
            # Else assume string and join list of strings to a single one
            field_value = ' '.join(input_data)

        if field.name == 'summary':
            summary_prefix = f'[{issue.key}]'

            # special case to strip the key prefix from the summary
            if field_value.startswith(summary_prefix):
                return field_value[len(summary_prefix):].strip()

        return field_value


    current_field = previous_field = None
    seen_fields = set()

    for line in editor_result_raw.splitlines():
        # Skip blank lines, comments, header/footer & conflict markers
        if not line.strip() or line.startswith(('#', '-'*10, '<<', '>>', '==')):
            continue

        # Parse a token from the current line
        parsed_token = ' '.join(line.split(' ')[0:4]).strip().replace('\u2800', '')

        if parsed_token in issue_fields_by_friendly:
            current_field = issue_fields_by_friendly[parsed_token]

            # Error if a field is found twice in the editor output
            if current_field in seen_fields:
                raise EditorRepeatFieldFound(current_field.name)

            # Track the fields already seen
            seen_fields.add(current_field)

            if previous_field:
                # Next field found, finish processing the previous field
                logger.debug('Read "%s" for Issue.%s', field_value, previous_field.name)  # type: ignore[unreachable]

                # If processing Issue conflicts in the editor, skip any fields which aren't in conflict
                if conflicts and previous_field.name not in conflicts:
                    logger.debug('Skipped %s, as not in conflict', previous_field.name)

                # Skip all readonly fields
                elif previous_field.metadata.get('readonly', False):
                    logger.debug('Skipped %s, as readonly', previous_field.name)

                else:
                    processed_value = preprocess_field(previous_field, field_value)

                    if not isinstance(processed_value, SkipEditorField):
                        editor_result[previous_field.name] = processed_value

            # Set local variables for next field
            previous_field = current_field
            field_value = []

            # Actual content starts after the token
            content_start = len(parsed_token) + 1
        else:
            # No valid token found, the whole line is content
            content_start = 0

        # Skip any lines before the first field is found
        if current_field:
            # Combine each line of content into a list
            field_value.append(line[content_start:].strip())


    return editor_result

'''
Print and text rendering utils for the CLI commands
Click library extension classes
'''
import dataclasses
import decimal
import logging
from typing import Any, cast, Dict, Hashable, List, Optional, Set

import arrow
import click
import pandas as pd
from tabulate import tabulate
import typing_inspect

from jira_offline.exceptions import EditorRepeatFieldFound, InvalidLsFieldInConfig
from jira_offline.jira import jira
from jira_offline.models import CustomFields, Issue, ProjectMeta
from jira_offline.utils import find_project, friendly_title, get_field_by_name
from jira_offline.utils.serializer import istype


logger = logging.getLogger('jira')


def print_list(df: pd.DataFrame, width: int=60, verbose: bool=False, include_project_col: bool=False,
               print_total: bool=False, print_filter: str=None) -> pd.DataFrame:
    '''
    Helper to print abbreviated list of issues

    Params:
        df:                   Issues to display in a DataFrame
        width:                Crop width for the summary string
        verbose:              Display more information
        include_project_col:  Include the Issue.project field in a column
        print_total:          Print the total count of records as text
    '''
    # Sort the output DataFrame by index. Also has side-effect of making a copy of the DataFrame, so
    # subsequent destructive changes can be made
    df = df.sort_index()

    if include_project_col:
        fields = ['project_key']
    else:
        fields = []

    if not verbose:
        fields += jira.config.display.ls_fields
    else:
        fields += jira.config.display.ls_fields_verbose
        width = 200

    def format_datetime(raw):
        if not raw or pd.isnull(raw):
            return ''
        dt = arrow.get(raw)
        if verbose:
            return f'{dt.format()}'
        else:
            return f'{dt.humanize()}'

    # Pretty dates
    df['updated'] = df.updated.apply(format_datetime)

    # Shorten the summary field for printing
    df['summary'] = df.summary.str.slice(0, width)

    def abbrev_key(key):
        if key is None:
            return ''
        if len(key) == 36:
            return key[0:8]
        return key

    # Abbreviate long issue keys (offline-created issues have a UUID as the key)
    df['key'] = df.key.apply(abbrev_key)
    df.set_index('key', inplace=True)
    df['epic_link'] = df.epic_link.apply(abbrev_key)
    df['parent_link'] = df.parent_link.apply(abbrev_key)

    if verbose:
        df.fix_versions = df.fix_versions.apply(lambda x: '' if x is None else ','.join(x))

    # Rename all extended customfield columns, removing the "extended." prefix
    df.rename(columns={f'extended.{f}': f for f in jira.config.iter_customfields()}, inplace=True)

    try:
        print_table(df[fields])
    except KeyError as e:
        raise InvalidLsFieldInConfig(e)

    if print_filter:
        print_filter = f'Filter: {print_filter}'

        if print_total:
            click.echo(f'Total issues {len(df)} ({print_filter.lower()})')
        else:
            click.echo(print_filter)

    elif print_total:
        click.echo(f'Total issues {len(df)}')

    # Make this function testable by returning the DataFrame
    return df[fields]


def print_table(df: pd.DataFrame):
    '''Helper to pretty print dataframes'''
    click.echo(tabulate(df, headers='keys', tablefmt='psql'))


def print_diff(issue: Issue):
    '''
    Build and render a diff of the passed issue.
    '''
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

    # Create dict mapping Issue attribute friendly names to the attribute name
    # Skip all internal tracking fields
    issue_fields_by_friendly: Dict[str, str] = {
        friendly_title(Issue, f.name):f.name
        for f in dataclasses.fields(Issue)
        if f.name not in ('extended', 'original', 'diff_to_original', '_active', 'modified')
    }

    if issue.extended:
        # Include all extended customfields defined on this issue
        issue_fields_by_friendly.update(
            {friendly_title(Issue, k):f'extended.{k}' for k in issue.extended.keys()}
        )

    editor_result: Dict[str, List[str]] = {}

    def preprocess_field(field_name: str, input_data: List[str]) -> Any:
        try:
            # Extract the dataclasses.field for this Issue attribute, to use the type for preprocessing
            field = get_field_by_name(Issue, field_name)
            is_extended = False

            # cast for mypy as istype uses @functools.lru_cache
            typ = cast(Hashable, field.type)

        except ValueError:
            # ValueError means this field_name must be an extended customfield
            is_extended = True
            typ = str

        # Validate empty
        if input_data in ('', ['']):
            if is_extended:
                return None

            if not typing_inspect.is_optional_type(field.type):
                # Field is mandatory, and editor returned blank - skip this field
                return SkipEditorField()
            elif field.default_factory != dataclasses.MISSING:  # type: ignore[misc] # https://github.com/python/mypy/issues/6910
                return field.default_factory()  # type: ignore[misc]
            else:
                return field.default

        if istype(typ, set):
            return {item[1:].strip() for item in input_data if len(item[1:].strip()) > 0}

        if istype(typ, list):
            return [item[1:].strip() for item in input_data if len(item[1:].strip()) > 0]

        if istype(typ, (int, decimal.Decimal)):
            # Handle number types
            field_value = input_data[0]
        else:
            # Else assume string and join list of strings to a single one
            field_value = ' '.join(input_data)

        if field_name == 'summary':
            summary_prefix = f'[{issue.key}]'

            # special case to strip the key prefix from the summary
            if field_value.startswith(summary_prefix):
                return field_value[len(summary_prefix):].strip()

        return field_value


    current_field: Optional[str] = None
    previous_field: Optional[str] = None
    field_value: List = []
    seen_fields: Set[str] = set()

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
                raise EditorRepeatFieldFound(current_field)

            # Track the fields already seen
            seen_fields.add(current_field)

            if previous_field:
                # Next field found, finish processing the previous field
                logger.debug('Read "%s" for Issue.%s', field_value, previous_field)

                try:
                    # Extract the dataclasses.field for this Issue attribute, and skip readonlys
                    skip_readonly = False
                    if get_field_by_name(Issue, previous_field).metadata.get('readonly', False):
                        skip_readonly = True
                except ValueError:
                    pass

                # If processing Issue conflicts in the editor, skip any fields which aren't in conflict
                if conflicts and previous_field not in conflicts:
                    logger.debug('Skipped %s, as not in conflict', previous_field)

                elif skip_readonly:
                    logger.debug('Skipped %s, as readonly', previous_field)

                else:
                    processed_value = preprocess_field(previous_field, field_value)

                    if not isinstance(processed_value, SkipEditorField):
                        editor_result[previous_field] = processed_value

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


class ValidCustomfield(click.Option):
    '''
    Validating click command line option for dynamic customfield parameters.

    Compatible CLI commands must pass either `Issue.key` or `ProjectMeta.key`. As customfields are
    found at `Issue.project.customfields`, a call to `jira.load_issues` must be executed.
    '''
    def handle_parse_result(self, ctx, opts, args):
        if 'key' in opts:
            # Load ProjectMeta instance via Issue.key
            jira.load_issues()
            issue = self._get_issue(opts['key'])
            project = issue.project

        elif 'projectkey' in opts:
            # Load ProjectMeta instance by ProjectMeta.key
            project = self._get_project(opts['projectkey'])

        else:
            raise Exception('ValidCustomfield constructor must be passed `key` or `projectkey`')

        # Iterate all configured customfields
        for customfield_name in jira.config.iter_customfields():
            # If one was passed as a CLI parameter..
            if opts.get(customfield_name):
                try:
                    # Validate for the project by issue key or project key
                    assert project.customfields[customfield_name]
                except KeyError:
                    raise click.UsageError(
                        f"Option '--{customfield_name.replace('_', '-')}' is not available on project {project.key}"
                    )

        return super().handle_parse_result(ctx, opts, args)

    def _get_issue(self, key: str) -> Issue:  # pylint: disable=no-self-use
        if key not in jira:
            raise click.UsageError('Unknown issue key')

        return cast(Issue, jira[key])

    def _get_project(self, projectkey: str) -> ProjectMeta:  # pylint: disable=no-self-use
        return find_project(jira, projectkey)


class CustomfieldsAsOptions(click.Command):
    '''
    Add configured customfields as optional CLI parameters
    '''
    def __init__(self, *args, **kwargs):
        for customfield_name in jira.config.iter_customfields():
            try:
                # Extract help text if defined on Customfields class
                f = get_field_by_name(CustomFields, customfield_name)
                help_text = f.metadata['cli_help']
            except ValueError:
                # Dynamic user-defined customfields have no help text
                help_text = ''

            kwargs['params'].insert(
                len(kwargs['params'])-3,  # insert above global_options
                ValidCustomfield([f"--{customfield_name.replace('_', '-')}"], help=help_text),
            )

        super().__init__(*args, **kwargs)

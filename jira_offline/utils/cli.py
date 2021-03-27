'''
Print and text rendering utils for the CLI commands
'''
import arrow
import click
import pandas as pd
from tabulate import tabulate

from jira_offline.models import Issue


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

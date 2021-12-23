'''
Module containing the lint command group, and all its subcommands
'''
import logging

import click

from jira_offline.cli.params import CliParams, filter_option, global_options
from jira_offline.jira import jira
from jira_offline.linters import fix_versions as lint_fix_versions
from jira_offline.linters import issues_missing_epic as lint_issues_missing_epic
from jira_offline.utils.cli import print_list


logger = logging.getLogger('jira')


@click.group(name='lint')
@click.option('--fix', is_flag=True, help='Attempt to fix the errors automatically')
@click.pass_context
@global_options
@filter_option
def cli_lint(ctx: click.core.Context, fix: bool=False):
    'Report on common mistakes in Jira issues'
    ctx.obj.lint = CliParams.LintParams(fix=fix)

    # load issues here for all subcommands in the group
    jira.load_issues()

    if jira.df.empty:
        click.echo('No issues in the cache')
        raise click.Abort


@cli_lint.command(name='fix-versions')
@click.option('--value', help='Value set in fix_versions. Used with --fix.')
@click.pass_context
@global_options
@filter_option
def cli_lint_fix_versions(ctx: click.core.Context, value: str=None):
    '''
    Lint on missing fix_versions field
    '''
    if ctx.obj.lint.fix and not value:
        raise click.BadParameter('You must pass --value with --fix', ctx)

    if value:
        if not ctx.obj.lint.fix:
            logger.warning('Passing --value without --fix has no effect')

    # query issues missing the fix_versions field
    df = lint_fix_versions(fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_fix_versions(fix=ctx.obj.lint.fix, value=value)

        click.echo(f'Updated fix_versions on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing the fix_versions field')

    if ctx.obj.verbose:
        print_list(df)


@cli_lint.command(name='issues-missing-epic')
@click.option('--epic-link', help='Epic to set on issues with no epic. Used with --fix.')
@click.pass_context
@global_options
@filter_option
def cli_lint_issues_missing_epic(ctx: click.core.Context, epic_link: str=None):
    '''
    Lint issues without an epic set
    '''
    if ctx.obj.lint.fix and not epic_link:
        raise click.BadParameter('You must pass --epic_link with --fix', ctx)

    if epic_link:
        if not ctx.obj.lint.fix:
            logger.warning('Passing --epic-link without --fix has no effect')

    # query issues missing the epic field
    df = lint_issues_missing_epic(fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_issues_missing_epic(fix=ctx.obj.lint.fix, epic_link=epic_link)

        click.echo(f'Set epic to {epic_link} on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing an epic')

    if ctx.obj.verbose:
        print_list(df)

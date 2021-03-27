'''
Module containing the lint command group, and all its subcommands
'''
import logging

import click

from jira_offline.cli.params import CliParams
from jira_offline.jira import jira
from jira_offline.linters import fix_versions as lint_fix_versions
from jira_offline.linters import issues_missing_epic as lint_issues_missing_epic
from jira_offline.utils.cli import print_list


logger = logging.getLogger('jira')


@click.group(name='lint')
@click.option('--fix', is_flag=True, help='Attempt to fix the errors automatically')
@click.option('--project', help='Filter for a specific project')
@click.pass_context
def cli_lint(ctx, fix: bool=False, project: str=None):
    'Report on common mistakes in Jira issues'
    ctx.obj.lint = CliParams.LintParams(fix=fix)

    # filter issues by project
    jira.filter.project_key = project

    # load issues here for all subcommands in the group
    jira.load_issues()

    if jira.df.empty:
        click.echo('No issues in the cache')
        raise click.Abort


@cli_lint.command(name='fix-versions')
@click.option('--value', help='Value set in fix_versions. Used with --fix.')
@click.pass_context
def cli_lint_fix_versions(ctx, value: str=None):
    '''
    Lint on missing fix_versions field
    '''
    if ctx.obj.lint.fix and not value:
        raise click.BadParameter('You must pass --value with --fix', ctx)

    if value:
        if not ctx.obj.lint.fix:
            logger.warning('Passing --value without --fix has no effect')

    # query issues missing the fix_versions field
    df = lint_fix_versions(jira, fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_fix_versions(jira, fix=ctx.obj.lint.fix, value=value)

        click.echo(f'Updated fix_versions on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing the fix_versions field')

    if ctx.obj.verbose:
        print_list(df)


@cli_lint.command(name='issues-missing-epic')
@click.option('--epic-ref', help='Epic to set on issues with no epic. Used with --fix.')
@click.pass_context
def cli_lint_issues_missing_epic(ctx, epic_ref: str=None):
    '''
    Lint issues without an epic set
    '''
    if ctx.obj.lint.fix and not epic_ref:
        raise click.BadParameter('You must pass --epic_ref with --fix', ctx)

    if epic_ref:
        if not ctx.obj.lint.fix:
            logger.warning('Passing --epic-ref without --fix has no effect')

    # query issues missing the epic field
    df = lint_issues_missing_epic(jira, fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_issues_missing_epic(jira, fix=ctx.obj.lint.fix, epic_ref=epic_ref)

        click.echo(f'Set epic to {epic_ref} on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing an epic')

    if ctx.obj.verbose:
        print_list(df)

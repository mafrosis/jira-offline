'''
Application CLI entrypoint. Uses the click library to configure commands and subcommands, arguments,
options and help text.
'''
from dataclasses import dataclass, field
import logging
from typing import Optional, Set

import click
import pandas as pd
from tabulate import tabulate

from jira_cli.config import load_config
from jira_cli.create import create_issue
from jira_cli.linters import fixversions as lint_fixversions
from jira_cli.linters import issues_missing_epic as lint_issues_missing_epic
from jira_cli.main import Jira
from jira_cli.sync import pull_issues, push_issues


logger = logging.getLogger('jira')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.ERROR)


@dataclass
class LintParams:
    fix: bool

@dataclass
class CliParams:
    verbose: bool = field(default=False)
    debug: bool = field(default=False)
    lint: Optional[LintParams] = field(default=None)

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Display INFO level logging')
@click.option('--debug', '-d', is_flag=True, help='Display DEBUG level logging')
@click.pass_context
def cli(ctx, verbose: bool=False, debug: bool=False):
    '''Base CLI options'''
    # setup the logger
    formatter = logging.Formatter('%(levelname)s: %(message)s')

    # handle --verbose and --debug
    if verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    if debug:
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter(f'%(levelname)s: {__name__}:%(lineno)s - %(message)s')

    sh.setFormatter(formatter)
    ctx.obj = CliParams(verbose=verbose, debug=debug)


@cli.command(name='show')
@click.argument('key')
def cli_show(key):
    '''Pretty print an Issue on the CLI'''
    jira = Jira()
    jira.load_issues()
    click.echo(jira[key])


@cli.command(name='push')
@click.pass_context
def cli_push(ctx):
    '''Synchronise changes back to Jira server'''
    jira = Jira()
    jira.config = load_config()
    jira.load_issues()
    push_issues(jira, verbose=ctx.obj.verbose)


@cli.command(name='clone')
@click.argument('project')
@click.option('--login', is_flag=True, help='Reset the current login credentials')
@click.pass_context
def cli_clone(ctx, project: str, login: bool=False):
    '''
    Clone a Jira project to offline

    PROJECT - Jira project key to configure and pull
    '''
    if ',' in project:
        click.echo('You should pass only a single project key')
        raise click.Abort

    jira = Jira()
    jira.config = load_config(prompt_for_creds=login)

    # pull the single project
    pull_issues(jira, projects={project}, verbose=ctx.obj.verbose)


@cli.command(name='pull')
@click.option('--projects', help='Jira project keys')
@click.option('--login', is_flag=True, help='Reset the current login credentials')
@click.option('--reset-hard', is_flag=True, help='Force reload of all issues. This will destroy any local changes!')
@click.pass_context
def cli_pull(ctx, projects: str=None, login: bool=False, reset_hard: bool=False):
    '''Fetch and cache all Jira issues'''
    projects_set: Optional[Set[str]] = None
    if projects:
        projects_set = set(projects.split(','))

    if reset_hard:
        click.confirm('Warning! This will destroy any local changes. Continue?', abort=True)

    jira = Jira()
    jira.config = load_config(prompt_for_creds=login)
    pull_issues(jira, projects=projects_set, force=reset_hard, verbose=ctx.obj.verbose)


@cli.command(name='new')
@click.argument('project')
@click.argument('issuetype')
@click.argument('summary')
@click.option('--assignee', help='Username of person assigned to complete the Issue')
@click.option('--description', help='Long description of Issue')
@click.option('--epic-name', help='Short epic name')
@click.option('--epic-ref', help='Epic key to which this Issue belongs')
@click.option('--estimate', help='Issue size estimate in story points', type=int)
@click.option('--fix-versions', help='Issue fix versions as comma-separated')
@click.option('--labels', help='Issue labels as comma-separated')
@click.option('--reporter', help='Username of Issue reporter (defaults to creator)')
def cli_new(project: str, issuetype: str, summary: str, **kwargs):
    '''
    Create a new issue on a project

    PROJECT    Jira project key for the new issue
    ISSUETYPE  A valid issue type for the specified project
    SUMMARY    Mandatory free text oneliner for this issue
    '''
    jira = Jira()
    jira.config = load_config()

    if ',' in project:
        click.echo('You should pass only a single project key')
        raise click.Abort

    if jira.config and project not in jira.config.projects:
        msg = (
            'The project {new} is not currently configured! You must first load the project with '
            'this command:\n\n  jiracli clone {new}\n'.format(new=project)
        )
        click.echo(msg)
        raise click.Abort

    # validate epic parameters
    if issuetype == 'Epic':
        if kwargs.get('epic_ref'):
            click.echo('You cannot pass --epic-ref when creating an Epic!')
            raise click.Abort
        if not kwargs.get('epic_name'):
            click.echo('You must pass --epic-name when creating an Epic!')
            raise click.Abort
    else:
        if kwargs.get('epic_name'):
            click.echo('Parameter --epic-name is ignored for anything other than an Epic')

    # parse fixVersions and labels
    if kwargs.get('fix_versions'):
        # note key change of --fix_versions -> Issue.fixVersions
        kwargs['fixVersions'] = set(kwargs['fix_versions'].split(','))
        del kwargs['fix_versions']
    if kwargs.get('labels'):
        kwargs['labels'] = set(kwargs['labels'].split(','))

    # create an Issue offline, it is sync'd on push
    new_issue = create_issue(jira, project, issuetype, summary, **kwargs)

    # display the new issue
    click.echo(new_issue)


@cli.group(name='stats', invoke_without_command=True)
@click.pass_context
def cli_group_stats(ctx):
    '''Generate stats on Jira data'''
    ctx.obj.jira = Jira()
    ctx.obj.jira.load_issues()

    if ctx.invoked_subcommand is None:
        for subcommand in (cli_stats_issuetype, cli_stats_status, cli_stats_fixversions):
            ctx.invoke(subcommand)

@cli_group_stats.command(name='issuetype')
@click.pass_context
def cli_stats_issuetype(ctx):
    '''Stats on issue type'''
    jira = ctx.obj.jira
    aggregated_issuetype = jira.df.groupby([jira.df.issuetype]).size().to_frame(name='count')
    _print_table(aggregated_issuetype)

@cli_group_stats.command(name='status')
@click.pass_context
def cli_stats_status(ctx):
    '''Stats on ticket status'''
    jira = ctx.obj.jira
    aggregated_status = jira.df.groupby([jira.df.status]).size().to_frame(name='count')
    _print_table(aggregated_status)

@cli_group_stats.command(name='fixversions')
@click.pass_context
def cli_stats_fixversions(ctx):
    '''Stats on ticket fixversions'''
    jira = ctx.obj.jira
    jira.df.fixVersions = jira.df.fixVersions.apply(lambda x: ','.join(x) if x else '')
    aggregated_fixVersions = jira.df.groupby([jira.df.fixVersions]).size().to_frame(name='count')
    _print_table(aggregated_fixVersions)


@cli.group(name='lint')
@click.option('--fix', is_flag=True, help='Attempt to fix the errors automatically')
@click.pass_context
def cli_group_lint(ctx, fix=False):
    'Report on common mistakes in Jira issues'
    ctx.obj.lint = LintParams(fix=fix)

@cli_group_lint.command(name='fixversions')
@click.option('--words', help='Words to look for in an Epic name, and set in fixVersions. Used with --fix.')
@click.pass_context
def cli_group_lint_fixversions(ctx, words=None):
    '''
    Lint on missing fixVersions field
    '''
    if ctx.obj.lint.fix and not words:
        raise click.BadParameter('You must pass --words with --fix', ctx)

    if words:
        if not ctx.obj.lint.fix:
            logger.warning('Passing --words without --fix has no effect')
        words = set(words.split(','))

    # query issues missing the fixVersions field
    df = lint_fixversions(fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_fixversions(ctx.obj.lint.fix, words)

        click.echo(f'Updated fixVersions on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing the fixVersions field')

    if ctx.obj.verbose:
        _print_list(df)

@cli_group_lint.command(name='issues-missing-epic')
@click.option('--epic-ref', help='Epic to set on issues with no epic. Used with --fix.')
@click.pass_context
def cli_group_lint_issues_missing_epic(ctx, epic_ref=None):
    '''
    Lint issues without an epic set
    '''
    if ctx.obj.lint.fix and not epic_ref:
        raise click.BadParameter('You must pass --epic_ref with --fix', ctx)

    if epic_ref:
        if not ctx.obj.lint.fix:
            logger.warning('Passing --epic-ref without --fix has no effect')

    # query issues missing the epic field
    df = lint_issues_missing_epic(fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_issues_missing_epic(ctx.obj.lint.fix, epic_ref)

        click.echo(f'Set epic to {epic_ref} on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing an epic')

    if ctx.obj.verbose:
        _print_list(df)


@cli.command(name='ls')
def cli_ls():
    '''List Issues on the CLI'''
    jira = Jira()
    jira.load_issues()
    _print_list(jira.df)


def _print_list(df: pd.DataFrame, width=100):
    '''Helper to print abbreviated list of issues'''
    # shorten the summary field for printing
    df['summary'] = df.loc[:]['summary'].str.slice(0, width)
    _print_table(df[['issuetype', 'summary', 'assignee', 'updated']])


def _print_table(df):
    '''Helper to pretty print dataframes'''
    click.echo(tabulate(df, headers='keys', tablefmt='psql'))

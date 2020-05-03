'''
Application CLI entrypoint. Uses the click library to configure commands and subcommands, arguments,
options and help text.
'''
import dataclasses
import json
import logging
from typing import Optional, Set
from urllib.parse import urlparse

import arrow
import click
import pandas as pd
from tabulate import tabulate

from jira_offline.auth import authenticate
from jira_offline.create import create_issue, find_epic_by_reference, set_field_on_issue
from jira_offline.exceptions import CliError, FailedPullingProjectMeta, JiraApiError, ProjectNotConfigured
from jira_offline.linters import fixversions as lint_fixversions
from jira_offline.linters import issues_missing_epic as lint_issues_missing_epic
from jira_offline.main import Jira
from jira_offline.models import ProjectMeta
from jira_offline.sync import pull_issues, pull_single_project, push_issues


logger = logging.getLogger('jira')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.ERROR)


@dataclasses.dataclass
class LintParams:
    fix: bool

@dataclasses.dataclass
class CliParams:
    verbose: bool = dataclasses.field(default=False)
    debug: bool = dataclasses.field(default=False)
    lint: Optional[LintParams] = dataclasses.field(default=None)

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Display INFO level logging')
@click.option('--debug', '-d', is_flag=True, help='Display DEBUG level logging')
@click.pass_context
def cli(ctx, verbose: bool=False, debug: bool=False):
    '''Base CLI options'''
    # setup the logger
    formatter = logging.Formatter('%(levelname)s: %(message)s')

    # handle --verbose and --debug
    if debug:
        verbose = True
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s: %(module)s:%(lineno)s - %(message)s')

    elif verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    sh.setFormatter(formatter)
    ctx.obj = CliParams(verbose=verbose, debug=debug)


@cli.command(name='show')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.argument('key')
def cli_show(key, as_json: bool=False):
    '''
    Pretty print an Issue on the CLI

    KEY - Jira issue key
    '''
    jira = Jira()
    jira.load_issues()

    if key not in jira:
        click.echo('Unknown issue key')
        raise click.Abort

    if as_json:
        output = jira[key].as_json()
    else:
        output = str(jira[key])

    click.echo(output)


@cli.command(name='push')
@click.pass_context
def cli_push(ctx):
    '''Synchronise changes back to Jira server'''
    jira = Jira()
    jira.load_issues()

    if not jira:
        click.echo('No issues in the cache')
        raise click.Abort

    push_issues(jira, verbose=ctx.obj.verbose)


@cli.command(name='projects')
@click.pass_context
def cli_projects(ctx):
    '''
    View currently cloned projects
    '''
    jira = Jira()
    if ctx.obj.verbose:
        for p in jira.config.projects.values():
            click.echo(p)
    else:
        click.echo(tabulate(
            [(p.key, p.name, p.project_uri) for p in jira.config.projects.values()],
            headers=['Key', 'Name', 'Project URI'],
            tablefmt='psql'
        ))


@cli.command(name='clone')
@click.argument('project_uri')
@click.option('--username', help='Basic auth username to authenicate with')
@click.option('--password', help='Basic auth password (use with caution!)')
@click.option('--oauth-app', default='jira-offline', help='Jira Application Link consumer name')
@click.option('--oauth-private-key', help='oAuth private key', type=click.Path(exists=True))
@click.option('--ca-cert', help='Custom CA cert for the Jira server', type=click.Path(exists=True))
@click.pass_context
def cli_clone(ctx, project_uri: str, username: str=None, password: str=None, oauth_app: str=None,
              oauth_private_key: str=None, ca_cert: str=None):
    '''
    Clone a Jira project to offline

    PROJECT - Jira project key to configure and pull
    '''
    uri = urlparse(project_uri)

    if username and oauth_private_key:
        click.echo('You cannot supply both username and oauth params together')
        raise click.Abort

    if not uri.scheme or not uri.netloc or not uri.path:
        click.echo((
            'Badly formed Jira project URI passed, must be of the form:\n'
            '  https://jira.atlassian.com:8080/PROJ'
        ))
        raise click.Abort

    # create a new project
    project = ProjectMeta(
        key=uri.path[1:],
        protocol=uri.scheme,
        hostname=uri.netloc,
    )
    # store CA cert, if supplied for this Jira
    if ca_cert:
        project.set_ca_cert(ca_cert)

    jira = Jira()
    if project.id in jira.config.projects:
        click.echo(f'Already cloned {project.project_uri}')
        raise click.Abort

    click.echo(f'Cloning project {project.key} from {project.jira_server}')
    authenticate(project, username, password, oauth_app, oauth_private_key)
    click.echo(f'Authenticated with {project.jira_server}')

    try:
        # retrieve project metadata
        jira.get_project_meta(project)
    except JiraApiError as e:
        raise FailedPullingProjectMeta(e)

    click.echo(f'{project.key} project properties retrieved')

    # write new project to the app config
    jira.config.projects[project.id] = project
    jira.config.write_to_disk()

    # and finally pull all the project's issues
    click.echo('Pulling issues..')
    pull_single_project(jira, project, force=False, verbose=ctx.obj.verbose)


@cli.command(name='pull')
@click.option('--projects', help='Jira project keys')
@click.option('--reset-hard', is_flag=True, help='Force reload of all issues. This will destroy any local changes!')
@click.pass_context
def cli_pull(ctx, projects: str=None, reset_hard: bool=False):
    '''Fetch and cache all Jira issues'''
    jira = Jira()

    projects_set: Optional[Set[str]] = None
    if projects:
        projects_set = set(projects.split(','))

        # validate all requested projects are configured
        for key in projects_set:
            if key not in {p.key for p in jira.config.projects.values()}:
                raise ProjectNotConfigured(key)

    if reset_hard:
        if projects:
            reset_warning = '\n'.join(projects_set)  # type: ignore
        else:
            reset_warning = '\n'.join([p.key for p in jira.config.projects.values()])  # type: ignore

        if reset_warning:
            click.confirm(
                f'Warning! This will destroy any local changes for project(s)\n\n{reset_warning}\n\nContinue?',
                abort=True
            )

    pull_issues(jira, projects=projects_set, force=reset_hard, verbose=ctx.obj.verbose)


@cli.command(name='new')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.argument('projectkey')
@click.argument('issuetype')
@click.argument('summary')
@click.option('--assignee', help='Username of person assigned to complete the Issue')
@click.option('--description', help='Long description of Issue')
@click.option('--epic-name', help='Short epic name')
@click.option('--epic-ref', help='Epic key to which this Issue belongs')
@click.option('--estimate', help='Issue size estimate in story points', type=int)
@click.option('--fix-versions', help='Issue fix versions as comma-separated')
@click.option('--labels', help='Issue labels as comma-separated')
@click.option('--priority', help='Set the priority of the issue')
@click.option('--reporter', help='Username of Issue reporter (defaults to creator)')
def cli_new(projectkey: str, issuetype: str, summary: str, as_json: bool=False, **kwargs):
    '''
    Create a new issue on a project

    PROJECTKEY    Jira project key for the new issue
    ISSUETYPE  A valid issue type for the specified project
    SUMMARY    Mandatory free text oneliner for this issue
    '''
    if ',' in projectkey:
        click.echo('You should pass only a single project key')
        raise click.Abort

    jira = Jira()

    try:
        # extract the ProjectMeta object for the specified project
        project: ProjectMeta = next(iter(
            [pm for id, pm in jira.config.projects.items() if pm.key == projectkey]
        ))
    except StopIteration:
        raise ProjectNotConfigured(projectkey)

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
    if as_json:
        output = new_issue.as_json()
    else:
        output = str(new_issue)

    click.echo(output)


@cli.command(name='edit')
@click.argument('key')
@click.option('--assignee', help='Username of person assigned to complete the Issue')
@click.option('--description', help='Long description of Issue')
@click.option('--epic-name', help='Short epic name')
@click.option('--epic-ref', help='Epic key to which this Issue belongs')
@click.option('--estimate', help='Issue size estimate in story points', type=int)
@click.option('--fix-versions', help='Issue fix versions as comma-separated')
@click.option('--labels', help='Issue labels as comma-separated')
@click.option('--priority', help='Set the priority of the issue')
@click.option('--reporter', help='Username of Issue reporter')
@click.option('--summary', help='Summary one-liner for this issue')
@click.option('--status', help='Set issue status to any valid for the issuetype')
def cli_edit(key, **kwargs):
    '''
    Edit one or more fields on an issue

    KEY - Jira issue key
    '''
    jira = Jira()
    jira.load_issues()

    if key not in jira:
        raise CliError(f"Issue {key} doesn't exist!")

    # validate epic parameters
    if jira[key].issuetype == 'Epic':
        if kwargs.get('epic_ref'):
            click.echo('Parameter --epic-ref is ignored when modifing an Epic')
            del kwargs['epic_ref']
    else:
        if kwargs.get('epic_name'):
            click.echo('Parameter --epic-name is ignored for anything other than an Epic')

    # parse fixVersions and labels
    if kwargs.get('fix_versions'):
        # note key change of --fix-versions -> Issue.fixVersions
        kwargs['fixVersions'] = set(kwargs['fix_versions'].split(','))
        del kwargs['fix_versions']
    if kwargs.get('labels'):
        kwargs['labels'] = set(kwargs['labels'].split(','))

    for field_name, value in kwargs.items():
        set_field_on_issue(jira[key], field_name, value)

    # link issue to epic if --epic-ref was passed
    if kwargs.get('epic_ref'):
        matched_epic = find_epic_by_reference(jira, kwargs['epic_ref'])
        jira[key].epic_ref = matched_epic.key

    click.echo(jira[key])
    jira.write_issues()


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
@click.option('--value', help='Value set in fixVersions. Used with --fix.')
@click.pass_context
def cli_group_lint_fixversions(ctx, value=None):
    '''
    Lint on missing fixVersions field
    '''
    if ctx.obj.lint.fix and not value:
        raise click.BadParameter('You must pass --value with --fix', ctx)

    if value:
        if not ctx.obj.lint.fix:
            logger.warning('Passing --value without --fix has no effect')

    jira = Jira()
    jira.load_issues()

    # query issues missing the fixVersions field
    df = lint_fixversions(jira, fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_fixversions(jira, fix=ctx.obj.lint.fix, value=value)

        click.echo(f'Updated fixVersions on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing the fixVersions field')

    if ctx.obj.verbose:
        _print_list(df, verbose=ctx.obj.verbose)

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

    jira = Jira()
    jira.load_issues()

    # query issues missing the epic field
    df = lint_issues_missing_epic(jira, fix=False)
    initial_missing_count = len(df)

    if ctx.obj.lint.fix:
        df = lint_issues_missing_epic(jira, fix=ctx.obj.lint.fix, epic_ref=epic_ref)

        click.echo(f'Set epic to {epic_ref} on {initial_missing_count - len(df)} issues')
    else:
        click.echo(f'There are {len(df)} issues missing an epic')

    if ctx.obj.verbose:
        _print_list(df, verbose=ctx.obj.verbose)


@cli.command(name='ls')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.pass_context
def cli_ls(ctx, as_json: bool=False):
    '''List Issues on the CLI'''
    jira = Jira()
    jira.load_issues()
    if as_json:
        for issue in jira.values():
            click.echo(json.dumps(issue.serialize()))
    else:
        _print_list(jira.df, verbose=ctx.obj.verbose, include_project_col=len(jira.config.projects) > 1)


def _print_list(df: pd.DataFrame, width: int=60, verbose: bool=False, include_project_col: bool=False):
    '''
    Helper to print abbreviated list of issues

    Params:
        df:                   Issues to display in a DataFrame
        width:                Crop width for the summary string
        verbose:              Display more information
        include_project_col:  Include the Issue.project field in a column
    '''
    if df.empty:
        click.echo('No issues in the cache')
        raise click.Abort

    if include_project_col:
        fields = ['project']
    else:
        fields = []

    if not verbose:
        fields += ['issuetype', 'epic_ref', 'summary', 'assignee', 'updated']
    else:
        fields += [
            'issuetype', 'epic_ref', 'epic_name', 'summary', 'assignee', 'fixVersions', 'updated'
        ]
        width = 200

    # pretty dates for non-verbose
    def format_datetime(raw):
        if not raw or pd.isnull(raw):
            return ''
        dt = arrow.get(raw)
        if verbose:
            return f'{dt.format()}'
        else:
            return f'{dt.humanize()}'
    df.updated = df.updated.apply(format_datetime)

    # shorten the summary field for printing
    df.summary = df.loc[:]['summary'].str.slice(0, width)

    # abbreviate UUID issue keys (these are on offline-created Issues)
    def abbrev_key(key):
        if key is None:
            return ''
        if len(key) == 36:
            return key[0:8]
        return key
    df.set_index(df.key.apply(abbrev_key), inplace=True)
    df.epic_ref = df.epic_ref.apply(abbrev_key)

    if verbose:
        df.fixVersions = df.fixVersions.apply(lambda x: '' if not x else ','.join(x))

    _print_table(df[fields])


def _print_table(df):
    '''Helper to pretty print dataframes'''
    click.echo(tabulate(df, headers='keys', tablefmt='psql'))

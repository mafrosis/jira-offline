'''
Module containing the simple top-level commands which do not have any subcommands
'''
import json
import io
import logging
from typing import Optional, Set

import click
from tabulate import tabulate

from jira_offline.auth import authenticate
from jira_offline.cli.params import filter_option, global_options
from jira_offline.config import get_default_user_config_filepath, write_default_user_config
from jira_offline.create import create_issue, import_issue, patch_issue_from_dict
from jira_offline.exceptions import (BadProjectMetaUri, EditorFieldParseFailed, EditorNoChanges,
                                     FailedPullingProjectMeta, ImportFailed, JiraApiError)
from jira_offline.jira import jira
from jira_offline.models import Issue, ProjectMeta
from jira_offline.sync import pull_issues, pull_single_project, push_issues
from jira_offline.utils import find_project
from jira_offline.utils.cli import CustomfieldsAsOptions, parse_editor_result, print_diff, print_list


logger = logging.getLogger('jira')


@click.command(name='show', no_args_is_help=True)
@click.argument('key')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.pass_context
@global_options
def cli_show(_, key: str, as_json: bool=False):
    '''
    Pretty print an Issue on the CLI

    KEY - Jira issue key
    '''
    jira.load_issues()

    if key not in jira:
        click.echo('Unknown issue key')
        raise click.Abort

    if as_json:
        output = jira[key].as_json()
    else:
        output = str(jira[key])

    click.echo(output)


@click.command(name='ls')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.pass_context
@global_options
@filter_option
def cli_ls(ctx: click.core.Context, as_json: bool=False):
    '''List Issues on the CLI'''
    jira.load_issues()

    if len(jira) == 0:
        click.echo('No issues in the cache')
        raise click.Abort

    if not jira.filter.is_set:
        # Default filter from user configuration
        jira.filter.set(jira.config.display.ls_default_filter)

    if as_json:
        for issue in jira.values():
            click.echo(json.dumps(issue.serialize()))
    else:
        print_list(
            jira.df,
            verbose=ctx.obj.verbose,
            include_project_col=len(jira.config.projects) > 1,
            print_total=True,
            print_filter=jira.filter.filter,
        )


@click.command(name='diff')
@click.argument('key', required=False)
@click.pass_context
@global_options
def cli_diff(_, key: str=None):
    '''
    Show the diff between changes made locally and the remote issues on Jira
    '''
    jira.load_issues()

    if key:
        if key not in jira:
            click.echo('Unknown issue key')
            raise click.Abort

        if not jira[key].exists:
            click.echo('This issue is new, so no diff is available')
            raise click.Abort

        print_diff(jira[key])

    else:
        for issue in jira.values():
            if issue.diff_to_original and issue.exists:
                print_diff(issue)


@click.command(name='reset', no_args_is_help=True)
@click.argument('key')
@click.pass_context
@global_options
def cli_reset(_, key: str):
    '''
    Reset an issue back to the last-seen Jira version, dropping any changes made locally
    '''
    jira.load_issues()

    if key not in jira:
        click.echo('Unknown issue key')
        raise click.Abort

    # overwrite local changes with the original
    jira[key] = Issue.deserialize(jira[key].original)
    jira.write_issues()

    click.echo(f'Reset issue {key}')


@click.command(name='push')
@click.pass_context
@global_options
def cli_push(ctx: click.core.Context):
    '''Synchronise changes back to Jira server'''
    jira.load_issues()

    if not jira:
        click.echo('No issues in the cache')
        raise click.Abort

    push_issues(verbose=ctx.obj.verbose)


@click.command(name='projects')
@click.pass_context
@global_options
def cli_projects(ctx: click.core.Context):
    '''
    View currently cloned projects
    '''
    if ctx.obj.verbose:
        for p in jira.config.projects.values():
            click.echo(p)
    else:
        click.echo(tabulate(
            [(p.key, p.name, p.project_uri, p.last_updated) for p in jira.config.projects.values()],
            headers=['Key', 'Name', 'Project URI', 'Last Sync'],
            tablefmt='psql'
        ))


@click.command(name='config')
@click.option('--config', '-c', type=click.Path(), help='Write default configuration to PATH')
def cli_config(config: Optional[str]=None):
    '''
    Output a default config file into ~/.config/jira-offline/jira-offline.ini

    Set a custom path with the --config option
    '''
    if config is None:
        config = get_default_user_config_filepath()

    write_default_user_config(config)
    click.echo(f'User config written to {config}')


@click.command(name='clone', no_args_is_help=True)
@click.argument('project_uri')
@click.option('--username', help='Basic auth username to authenicate with')
@click.option('--password', help='Basic auth password (use with caution!)')
@click.option('--oauth-app', default='jira-offline', help='Jira Application Link consumer name')
@click.option('--oauth-private-key', help='oAuth private key', type=click.Path(exists=True))
@click.option('--ca-cert', help='Custom CA cert for the Jira server', type=click.Path(exists=True))
@click.option('--tz', help='Set the timezone for this Jira project (default: local system timezone)')
@click.pass_context
@global_options
def cli_clone(ctx: click.core.Context, project_uri: str, username: str=None, password: str=None, oauth_app: str=None,
              oauth_private_key: str=None, ca_cert: str=None, tz: str=None):
    '''
    Clone a Jira project to offline

    PROJECT_URI - Jira project URI to setup and pull issues from, for example: https://jira.atlassian.com:8080/PROJ
    '''
    if username and oauth_private_key:
        click.echo('You cannot supply both username and oauth params together')
        raise click.Abort

    try:
        project = ProjectMeta.factory(project_uri, tz)
    except BadProjectMetaUri as e:
        click.echo(e)
        raise click.Abort

    # store CA cert, if supplied for this Jira
    if ca_cert:
        project.set_ca_cert(ca_cert)

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
    pull_single_project(
        project, force=False, verbose=ctx.obj.verbose, page_size=jira.config.sync.page_size
    )


@click.command(name='pull')
@click.option('--projects', help='Jira project keys')
@click.option('--reset', is_flag=True, help='Force reload of all issues. This will destroy any local changes!')
@click.option('--no-retry', is_flag=True, help='Do not retry a Jira server which is unavailable')
@click.pass_context
@global_options
def cli_pull(ctx: click.core.Context, projects: str=None, reset: bool=False, no_retry: bool=False):
    '''Fetch and cache all Jira issues'''

    projects_set: Optional[Set[str]] = None
    if projects:
        projects_set = set(projects.split(','))

        # validate all requested projects are configured
        # find_project will raise an exception if the project key is unknown
        for key in projects_set:
            find_project(jira, key)

    if reset:
        if projects:
            reset_warning = '\n'.join(projects_set)  # type: ignore[arg-type]
        else:
            reset_warning = '\n'.join([p.key for p in jira.config.projects.values()])

        if reset_warning:
            click.confirm(
                f'Warning! This will destroy any local changes for project(s)\n\n{reset_warning}\n\nContinue?',
                abort=True
            )

    pull_issues(projects=projects_set, force=reset, verbose=ctx.obj.verbose, no_retry=no_retry)


@click.command(name='new', cls=CustomfieldsAsOptions, no_args_is_help=True)
@click.argument('projectkey')
@click.argument('issuetype')
@click.argument('summary')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.option('--assignee', help='Username of person assigned to the issue')
@click.option('--description', help='Long description of Issue')
@click.option('--fix-versions', help='Issue fix version as comma-separated list')
@click.option('--labels', help='Issue labels as comma-separated')
@click.option('--priority', help='Priority of the issue')
@click.option('--reporter', help='Username of issue reporter')
@click.pass_context
@global_options
def cli_new(_, projectkey: str, issuetype: str, summary: str, as_json: bool=False, **kwargs):
    '''
    Create a new issue on a project

    PROJECTKEY  Jira project on which to create the issue

    ISSUETYPE   A valid issue type for the specified project

    SUMMARY     Mandatory free text one-liner
    '''
    if ',' in projectkey:
        click.echo('You should pass only a single project key')
        raise click.Abort

    # retrieve the project configuration
    project = find_project(jira, projectkey)

    # validate epic parameters
    if issuetype == 'Epic':
        if kwargs.get('epic_link'):
            click.echo('You cannot pass --epic-link when creating an Epic!')
            raise click.Abort
        if not kwargs.get('epic_name'):
            click.echo('You must pass --epic-name when creating an Epic!')
            raise click.Abort
    else:
        if kwargs.get('epic_name'):
            click.echo('Parameter --epic-name is ignored for anything other than an Epic')

    # parse fix_versions and labels
    if kwargs.get('fix_versions'):
        kwargs['fix_versions'] = set(kwargs['fix_versions'].split(','))
    if kwargs.get('labels'):
        kwargs['labels'] = set(kwargs['labels'].split(','))

    # create an Issue offline, it is sync'd on push
    new_issue = create_issue(project, issuetype, summary, **kwargs)

    # display the new issue
    if as_json:
        output = new_issue.as_json()
    else:
        output = str(new_issue)

    click.echo(output)


@click.command(name='edit', cls=CustomfieldsAsOptions, no_args_is_help=True)
@click.argument('key')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.option('--editor', is_flag=True, help='Free edit all issue fields in your shell editor')
@click.option('--assignee', help='Username of person assigned to the issue')
@click.option('--description', help='Long description of issue')
@click.option('--fix-versions', help='Issue fix version as comma-separated list')
@click.option('--labels', help='Issue labels as comma-separated')
@click.option('--priority', help='Priority of the issue')
@click.option('--reporter', help='Username of issue reporter')
@click.option('--summary', help='Summary one-liner for this issue')
@click.option('--status', help='Valid status for the issue\'s type')
@click.pass_context
@global_options
def cli_edit(_, key: str, as_json: bool=False, editor: bool=False, **kwargs):
    '''
    Edit one or more fields on an issue

    KEY - Jira issue key
    '''
    jira.load_issues()

    if key not in jira:
        click.echo('Unknown issue key')
        raise click.Abort

    issue = jira[key]

    if editor:
        retry = 1
        while retry <= 3:
            try:
                # Display interactively in $EDITOR
                editor_result_raw = click.edit(tabulate(issue.render()))
                if not editor_result_raw:
                    raise EditorNoChanges

                # Parse the editor output into a dict
                patch_dict = parse_editor_result(issue, editor_result_raw)
                break

            except (EditorFieldParseFailed, EditorNoChanges) as e:
                logger.error(e)

                if not click.confirm(f'Try again?  (retry {retry} of 3)'):
                    return
            finally:
                retry += 1
    else:
        # Validate epic parameters
        if issue.issuetype == 'Epic':
            if kwargs.get('epic_link'):
                click.echo('Parameter --epic-link is ignored when modifing an Epic')
                del kwargs['epic_link']
        else:
            if kwargs.get('epic_name'):
                click.echo('Parameter --epic-name is ignored for anything other than an Epic')

        # Parse fix_versions and labels
        if kwargs.get('fix_versions'):
            kwargs['fix_versions'] = set(kwargs['fix_versions'].split(','))
        if kwargs.get('labels'):
            kwargs['labels'] = set(kwargs['labels'].split(','))

        patch_dict = kwargs

    # Patch the issue with fields from the CLI or editor
    patch_issue_from_dict(issue, patch_dict)
    issue.commit()

    jira.write_issues()

    if as_json:
        # Display the edited issue as JSON
        click.echo(issue.as_json())
    else:
        # Print diff of edited issue
        print_diff(issue)


@click.command(name='import', no_args_is_help=True)
@click.argument('file', type=click.File('r'))
@click.pass_context
@global_options
def cli_import(_, file: io.TextIOWrapper):
    '''
    Import issues from stdin, or from a filepath

    FILE  Jsonlines format file from which to import issues
    '''
    jira.load_issues()

    no_input = True
    write = False

    # verbose logging by default during import
    logger.setLevel(logging.INFO)

    for i, line in enumerate(file.readlines()):
        if line:
            no_input = False

            try:
                issue, is_new = import_issue(json.loads(line), lineno=i+1)
                write = True

                if is_new:
                    logger.info('New issue created: %s', issue.summary)
                else:
                    logger.info('Issue %s updated', issue.key)

            except json.decoder.JSONDecodeError as e:
                logger.error('Failed parsing line %s', i+1)
            except ImportFailed as e:
                logger.error(e)
        else:
            break

    if no_input:
        click.echo('No data read on stdin or in passed file')
        raise click.Abort

    if write:
        jira.write_issues()

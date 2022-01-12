'''
Module containing the simple top-level commands which do not have any subcommands
'''
from contextlib import redirect_stdout
import datetime
import json
import io
import logging
import os
from pathlib import Path
from typing import cast, Iterable, Optional, Set, Tuple, Union

import click
from click.shell_completion import shell_complete  # pylint: disable=no-name-in-module

from jira_offline.auth import authenticate
from jira_offline.edit import edit_issue
from jira_offline.cli.params import filter_option, force_option, global_options
from jira_offline.cli.project import cli_project_list
from jira_offline.config import get_default_user_config_filepath
from jira_offline.config.user_config import write_default_user_config
from jira_offline.create import create_issue, import_csv, import_jsonlines
from jira_offline.exceptions import (BadProjectMetaUri, FailedPullingProjectMeta, JiraApiError,
                                     NoInputDuringImport)
from jira_offline.jira import jira
from jira_offline.models import Issue, ProjectMeta
from jira_offline.sync import pull_issues, pull_single_project, push_issues
from jira_offline.utils import find_project
from jira_offline.utils.cli import (CustomfieldsAsOptions, EditClickCommand, prepare_df, print_diff,
                                    print_list)


logger = logging.getLogger('jira')


@click.command(name='show', no_args_is_help=True)
@click.argument('key')
@click.option('--json', 'as_json', '-j', is_flag=True, help='Print output in JSON format')
@click.pass_context
@global_options
def cli_show(_, key: str, as_json: bool=False):
    '''
    Pretty print an Issue on the CLI.

    KEY  Jira issue key
    '''
    jira.load_issues()

    if key not in jira:
        click.echo('Unknown issue key', err=True)
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
    '''List Issues on the CLI.'''
    jira.load_issues()

    if len(jira) == 0:
        click.echo('No issues in the cache', err=True)
        raise click.Abort

    if not jira.filter.is_set:
        # Default filter from user configuration
        jira.filter.set(jira.config.user_config.display.ls_default_filter)

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
    Show the diff between changes made locally and the remote issues on Jira.

    KEY  Jira issue key, if specified display diff for this issue only
    '''
    jira.load_issues()

    if key:
        if key not in jira:
            click.echo('Unknown issue key', err=True)
            raise click.Abort

        if not jira[key].exists:
            click.echo('This issue is new, so no diff is available', err=True)
            raise click.Abort

        print_diff(jira[key])

    else:
        # Display diff for all locally modified issues
        for issue_key in jira.df.loc[~jira.is_new() & jira.is_modified(), 'key']:
            print_diff(jira[issue_key])


@click.command(name='status')
@click.pass_context
@global_options
def cli_status(ctx: click.core.Context):
    '''
    Show locally modified issues.
    '''
    jira.load_issues()

    for issue in jira.values():
        if issue.exists is False:
            if ctx.obj.verbose:
                print(f'new issue:   {issue.key}')
            else:
                print(f'new issue:   {issue.key[0:8]}')
        elif issue.modified:
            print(f'modified:    {issue.key}')


@click.command(name='reset', no_args_is_help=True)
@click.argument('key')
@click.pass_context
@global_options
@force_option
def cli_reset(ctx: click.core.Context, key: str):
    '''
    Reset an issue back to the last seen Jira version, dropping any changes made locally.

    Passing the string "all" will reset ALL locally modified issues, and delete any new issues
    created offline.

    KEY  Jira issue key, or "all"
    '''
    jira.load_issues()

    issues: Tuple[Issue, ...]

    if key != 'all':
        if key not in jira:
            click.echo('Unknown issue key', err=True)
            raise click.Abort

        issues = (cast(Issue, jira[key]),)
    else:
        if not ctx.obj.force:
            click.confirm(
                'Warning! This will destroy any local changes for all projects!\n\nContinue?',
                abort=True
            )

        # Retrieve all new or modified Jira issues
        issues = tuple(
            cast(Issue, jira[k])
            for k in jira.df.loc[jira.is_new() | jira.is_modified(), 'key']
        )

    for issue in issues:
        if not issue.exists:
            # Delete new, local-only issues
            del jira[issue.key]
        else:
            # Overwrite local changes with the original issue from Jira
            jira[issue.key] = Issue.deserialize(issue.original, issue.project)

    jira.write_issues()

    if key != 'all':
        click.echo(f'Reset issue {key}')
    else:
        click.echo('Done')


@click.command(name='push')
@click.option('--dry-run', '-n', is_flag=True, help='Simulate a push, logging the data that would be sent to Jira API')
@click.option('--interactive', '-i', is_flag=True, help='Display a diff for each issue, and prompt to push or skip')
@click.pass_context
@global_options
def cli_push(_, dry_run: bool=False, interactive: bool=False):
    '''Synchronise changes back to Jira server.'''
    jira.load_issues()

    if not jira:
        click.echo('No issues in the cache', err=True)
        raise click.Abort

    push_issues(dry_run, interactive)


@click.command(name='projects')
@click.pass_context
@global_options
def cli_project_list_shortcut(ctx: click.core.Context):
    '''View currently cloned projects.'''
    # Shortcut to the `jira project list` subcommmand.
    ctx.forward(cli_project_list)


@click.command(name='config')
@click.option('--config', '-c', type=click.Path(), help='Write default configuration to PATH')
def cli_config(config: Optional[str]=None):
    '''
    Output a default config file into ~/.config/jira-offline/jira-offline.ini.

    Set a custom path with the --config option.
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
def cli_clone(_, project_uri: str, username: str=None, password: str=None, oauth_app: str=None,
              oauth_private_key: str=None, ca_cert: str=None, tz: str=None):
    '''
    Clone a Jira project to use offline.

    PROJECT_URI  Jira project URI to setup and pull issues from, for example: https://jira.atlassian.com:8080/PROJ
    '''
    if username and oauth_private_key:
        click.echo('You cannot supply both username and oauth params together', err=True)
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
        click.echo(f'Already cloned {project.project_uri}', err=True)
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
        project, force=False, page_size=jira.config.user_config.sync.page_size
    )


@click.command(name='pull')
@click.option('--projects', help='Jira project keys')
@click.option('--reset', is_flag=True, help='Force reload of all issues. This will destroy any local changes!')
@click.option('--no-retry', is_flag=True, help='Do not retry a Jira server which is unavailable')
@click.pass_context
@global_options
@force_option
def cli_pull(ctx: click.core.Context, projects: str=None, reset: bool=False, no_retry: bool=False):
    '''Fetch and cache all Jira issues.'''

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

        # Display warning if more than one project is configured, and force is False
        if reset_warning and not ctx.obj.force:
            click.confirm(
                f'Warning! This will destroy any local changes for project(s)\n\n{reset_warning}\n\nContinue?',
                abort=True
            )

    pull_issues(projects=projects_set, force=reset, no_retry=no_retry)


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
    Create a new issue on a project.

    \b
    PROJECTKEY  Jira project key
    ISSUETYPE   A valid issue type for the specified project
    SUMMARY     Mandatory free text one-liner
    '''
    if ',' in projectkey:
        click.echo('You should pass only a single project key', err=True)
        raise click.Abort

    # Retrieve the project configuration
    project = find_project(jira, projectkey)

    # Validate epic parameters
    if issuetype == 'Epic':
        if kwargs.get('epic_link'):
            click.echo('You cannot pass --epic-link when creating an Epic!', err=True)
            raise click.Abort
        if not kwargs.get('epic_name'):
            click.echo('You must pass --epic-name when creating an Epic!', err=True)
            raise click.Abort
    else:
        if kwargs.get('epic_name'):
            click.echo('Parameter --epic-name is ignored for anything other than an Epic', err=True)

    # Set a default reporter if defined for this project
    if not kwargs.get('reporter') and project.default_reporter:
        kwargs['reporter'] = project.default_reporter

    # Create an Issue offline, it is sync'd on push
    new_issue = create_issue(project, issuetype, summary, **kwargs)

    # Write changes to disk
    jira.write_issues()

    # Display the new issue
    if as_json:
        output = new_issue.as_json()
    else:
        output = str(new_issue)

    click.echo(output)


@click.command(name='edit', cls=EditClickCommand, no_args_is_help=True)
@click.argument('key', required=False)
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
@filter_option
def cli_edit(_, key: str, as_json: bool=False, editor: bool=False, **kwargs):
    '''
    Edit one or more fields on one or more issues.

    KEY  Jira issue key (optional if --filter is supplied)
    '''
    if editor and jira.filter.is_set:
        click.echo('Parameter --editor cannot be used in conjunction with --filter', err=True)
        raise click.Abort

    jira.load_issues()

    issues: Iterable[Issue]

    if jira.filter.is_set:
        issues = (jira[key] for key in jira.filter.apply().index)
    else:
        if key not in jira:
            click.echo(f'Unknown issue key: {key}', err=True)
            raise click.Abort

        issues = [jira[key]]

    for issue in issues:
        edit_issue(issue, kwargs, editor)

        if as_json:
            # Display the edited issue as JSON
            click.echo(issue.as_json())
        else:
            # Print diff of edited issue
            print_diff(issue)

    jira.write_issues()


@click.command(name='export', no_args_is_help=True)
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True, writable=True))
@click.pass_context
@global_options
@filter_option
def cli_export(_, directory: str):
    '''
    Export issues to CSV at DIRECTORY

    Supply the --filter argument with an SQL clause to filter the set of returned issues.
    '''
    jira.load_issues()

    df = prepare_df(jira.df, width=None, include_long_date=True, include_project_col=False)

    # Simply write the filtered DataFrame to CSV
    df.to_csv(
        os.path.join(directory, datetime.datetime.now().strftime('jira_export_%Y-%m-%d.csv')),
        index=True,
        header=True,
    )


@click.command(name='import', no_args_is_help=True)
@click.argument('filepath', type=click.Path(exists=True, dir_okay=False, allow_dash=True))
@click.option('--dry-run', '-n', is_flag=True, help="Don't actually import, just show the diff the import will create")
@click.option('--strict', is_flag=True, help='Stop on errors during import')
@click.pass_context
@global_options
def cli_import(ctx: click.core.Context, filepath: Union[str, int], dry_run: bool=False, strict: bool=False):
    '''
    Import issues from stdin, or from a filepath

    FILEPATH  JSONlines or CSV format file to import from. To read JSONlines from STDIN, pass a dash.
    '''
    jira.load_issues()

    # Interpret dash to mean read STDIN
    if filepath == '-':
        filepath = 0

    try:
        with open(filepath, encoding='utf8') as f:
            if filepath == 0 or filepath.endswith(('json', 'jsonl')):  # type: ignore[union-attr]
                imported_issues = import_jsonlines(f, verbose=ctx.obj.verbose, strict=strict)
            else:
                imported_issues = import_csv(f, verbose=ctx.obj.verbose, strict=strict)

    except NoInputDuringImport:
        click.echo('No data read on stdin or in passed file', err=True)
        raise click.Abort

    if imported_issues and dry_run:
        for issue in imported_issues:
            # Print new issues, and print a diff for modified issues
            if not issue.exists:
                print(issue)
            elif issue.modified:
                print_diff(issue)

    elif imported_issues:
        jira.write_issues()


@click.command(name='delete', no_args_is_help=True)
@click.argument('key')
@click.pass_context
@global_options
def cli_delete_issue(_, key: str):
    '''
    Delete an issue.

    KEY  Jira issue key
    '''
    jira.load_issues()

    if key not in jira:
        click.echo('Unknown issue key', err=True)
        raise click.Abort

    del jira[key]
    jira.write_issues()


@click.command(name='completion', no_args_is_help=True)
@click.argument('shell', type=click.Choice(['bash', 'zsh', 'fish']))
@click.option('--stdout', is_flag=True, help='Print the completion text on STDOUT')
@click.pass_context
def cli_completion(_, shell: str, stdout: bool=False):
    '''
    Generate shell completion file.

    SHELL  "bash", "zsh", or "fish"
    '''
    captured = io.StringIO()

    # Capture printed output from `shell_complete` function
    with redirect_stdout(captured):
        # Following call was determined by reading source code at:
        # https://github.com/pallets/click/blob/8.0.1/src/click/shell_completion.py#L44
        shell_complete(cli_completion, dict(), 'jira', 'None', f'{shell}_source')

    autocomplete_txt = captured.getvalue()

    if stdout:
        click.echo(autocomplete_txt)
        return

    if shell == 'fish':
        # Ensure the path to the fish completions exists
        config_dir = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
        Path(os.path.join(config_dir, 'fish', 'completions')).mkdir(parents=True, exist_ok=True)
        path = os.path.join(config_dir, 'fish', 'completions', 'foo-bar.fish')
    else:
        path = os.path.join(os.path.dirname(get_default_user_config_filepath()), f'jira-offline.{shell}')

    with open(path, 'w', encoding='utf8') as f:
        f.write(autocomplete_txt)

    if shell == 'fish':
        click.echo(f'Completion written to {path}')
    else:
        click.echo(f'Add the following to your .{shell}rc')
        click.echo(f'source {path}')

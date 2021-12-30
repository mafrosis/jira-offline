'''
Subcommand for project operations
'''
import click
from tabulate import tabulate

from jira_offline.auth import authenticate
from jira_offline.cli.params import force_option, global_options
from jira_offline.exceptions import ProjectNotConfigured
from jira_offline.jira import jira
from jira_offline.utils import find_project


@click.group(name='project')
@click.pass_context
@global_options
def cli_projects(_):
    '''
    Subcommand for project operations.
    '''

@cli_projects.command(name='list')
@click.pass_context
@global_options
def cli_project_list(ctx: click.core.Context):
    '''
    View currently cloned projects.
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


@cli_projects.command(name='update-auth', no_args_is_help=True)
@click.argument('projectkey')
@click.option('--username', help='Basic auth username to authenicate with')
@click.option('--password', help='Basic auth password (use with caution!)')
@click.option('--oauth-app', default='jira-offline', help='Jira Application Link consumer name')
@click.option('--oauth-private-key', help='oAuth private key', type=click.Path(exists=True))
@click.option('--ca-cert', help='Custom CA cert for the Jira server', type=click.Path(exists=True))
@click.pass_context
@global_options
def cli_project_update_auth(ctx: click.core.Context, projectkey: str, username: str=None,
                            password: str=None, oauth_app: str=None, oauth_private_key: str=None,
                            ca_cert: str=None):
    '''
    Update the authentication on a project.

    PROJECTKEY  Jira project key
    '''
    if username and oauth_private_key:
        click.echo('You cannot supply both username and oauth params together', err=True)
        raise click.Abort

    try:
        project = find_project(jira, projectkey)
    except ProjectNotConfigured:
        click.echo('Unknown project!', err=True)
        ctx.invoke(cli_project_list)
        raise click.Abort

    authenticate(project, username, password, oauth_app, oauth_private_key)
    click.echo(f'Authenticated with {project.jira_server}')

    # store CA cert, if supplied for this Jira
    if ca_cert:
        project.set_ca_cert(ca_cert)

    jira.config.write_to_disk()
    click.echo(f'Updated details for project {projectkey}')


@cli_projects.command(name='delete')
@click.argument('projectkey')
@click.pass_context
@global_options
@force_option
def cli_project_delete(ctx: click.core.Context, projectkey: str):
    '''
    Delete a cloned project from local storage.

    PROJECTKEY  Jira project key
    '''
    try:
        project = find_project(jira, projectkey)
    except ProjectNotConfigured:
        click.echo('Unknown project!', err=True)
        ctx.invoke(cli_project_list)
        raise click.Abort

    jira.load_issues()

    if not ctx.obj.force:
        click.confirm(
            f'Warning! This will delete all local issues for project {projectkey}\n\nContinue?',
            abort=True
        )

    del jira.config.projects[project.id]
    jira.config.write_to_disk()

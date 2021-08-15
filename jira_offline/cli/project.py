'''
Subcommand for project operations
'''
import click
from tabulate import tabulate

from jira_offline.cli.params import global_options
from jira_offline.jira import jira


@click.group(name='project')
@click.pass_context
@global_options
def cli_projects(_):
    '''
    Subcommand for project operations
    '''

@cli_projects.command(name='list')
@click.pass_context
@global_options
def cli_project_list(ctx: click.core.Context):
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


@cli_projects.command(name='delete')
@click.argument('projectkey')
@click.pass_context
@global_options
def cli_project_delete(ctx: click.core.Context, projectkey: str):
    '''
    Delete a cloned project from local storage
    '''
    project = next(p for p in jira.config.projects.values() if p.key == projectkey)
    if not project:
        click.echo('Unknown project!')
        ctx.invoke(cli_project_list)
        raise click.Abort

    jira.load_issues()

    # Access the private DataFrame so to be sure no filter is applied
    df = jira._df  # pylint: disable=protected-access

    if len(df[(df.project_key == projectkey) & (df.id > 0) & df.modified]):
        click.confirm('You have local modified changes which will be lost. Continue?', abort=True)

    del jira.config.projects[project.id]
    jira.config.write_to_disk()

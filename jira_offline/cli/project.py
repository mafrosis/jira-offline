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

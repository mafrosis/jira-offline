'''
Module containing the stats command group, and all its subcommands
'''
import click

from jira_offline.cli.params import filter_option, global_options
from jira_offline.jira import jira
from jira_offline.utils.cli import print_table


@click.group(name='stats', invoke_without_command=True)
@click.pass_context
@global_options
@filter_option
def cli_stats(ctx: click.core.Context):
    '''Generate stats on Jira data'''
    # load issues here for all subcommands in the group
    jira.load_issues()

    if jira.df.empty:
        click.echo('No issues in the cache')
        raise click.Abort

    if ctx.invoked_subcommand is None:
        for subcommand in (cli_stats_issuetype, cli_stats_status, cli_stats_fix_versions):
            ctx.invoke(subcommand)


@cli_stats.command(name='issuetype')
@click.pass_context
@global_options
@filter_option
def cli_stats_issuetype(_):
    '''Stats on issue type'''
    aggregated_issuetype = jira.df.groupby([jira.df.issuetype]).size().to_frame(name='count')
    print_table(aggregated_issuetype)


@cli_stats.command(name='status')
@click.pass_context
@global_options
@filter_option
def cli_stats_status(_):
    '''Stats on issue status'''
    aggregated_status = jira.df.groupby([jira.df.status]).size().to_frame(name='count')
    print_table(aggregated_status)


@cli_stats.command(name='fix-versions')
@click.pass_context
@global_options
@filter_option
def cli_stats_fix_versions(_):
    '''Stats on issue fix-versions'''
    jira.df.fix_versions = jira.df.fix_versions.apply(lambda x: ','.join(x) if x else '')
    aggregated_fix_versions = jira.df.groupby([jira.df.fix_versions]).size().to_frame(name='count')
    print_table(aggregated_fix_versions)

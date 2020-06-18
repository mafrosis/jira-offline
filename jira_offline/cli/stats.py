'''
Module containing the stats command group, and all its subcommands
'''
import click

from jira_offline.main import Jira
from jira_offline.utils.cli import print_table


@click.group(name='stats', invoke_without_command=True)
@click.pass_context
def cli_stats(ctx):
    '''Generate stats on Jira data'''
    ctx.obj.jira = Jira()
    ctx.obj.jira.load_issues()

    if ctx.invoked_subcommand is None:
        for subcommand in (cli_stats_issuetype, cli_stats_status, cli_stats_fix_versions):
            ctx.invoke(subcommand)


@cli_stats.command(name='issuetype')
@click.pass_context
def cli_stats_issuetype(ctx):
    '''Stats on issue type'''
    jira = ctx.obj.jira
    aggregated_issuetype = jira.df.groupby([jira.df.issuetype]).size().to_frame(name='count')
    print_table(aggregated_issuetype)


@cli_stats.command(name='status')
@click.pass_context
def cli_stats_status(ctx):
    '''Stats on ticket status'''
    jira = ctx.obj.jira
    aggregated_status = jira.df.groupby([jira.df.status]).size().to_frame(name='count')
    print_table(aggregated_status)


@cli_stats.command(name='fix-versions')
@click.pass_context
def cli_stats_fix_versions(ctx):
    '''Stats on issue fix-versions'''
    jira = ctx.obj.jira
    jira.df.fix_versions = jira.df.fix_versions.apply(lambda x: ','.join(x) if x else '')
    aggregated_fix_versions = jira.df.groupby([jira.df.fix_versions]).size().to_frame(name='count')
    print_table(aggregated_fix_versions)

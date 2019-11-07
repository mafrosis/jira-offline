import datetime
import logging

import click
from tabulate import tabulate

from jira_cli.main import Jira


logger = logging.getLogger('jira')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.ERROR)


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Display INFO level logging')
@click.option('--debug', '-d', is_flag=True, help='Display DEBUG level logging')
def cli(verbose: bool=False, debug: bool=False):
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


@cli.command(name='pull')
def cli_pull():
    '''Fetch and cache all JIRA issues'''
    dtstart = datetime.datetime.now()
    Jira.pull_issues()
    print('Query time: {}'.format(datetime.datetime.now() - dtstart))

@cli.group(name='stats')
def cli_group_stats():
    'Generate stats on JIRA data'

@cli_group_stats.command(name='issuetype')
def cli_stats_issuetype():
    '''Stats on issue type'''
    df = Jira.load_issues()
    aggregated_issuetype = df.groupby([df['issuetype']]).size().to_frame(name='count')
    _print_table(aggregated_issuetype)

@cli_group_stats.command(name='status')
def cli_stats_status():
    '''Stats on ticket status'''
    df = Jira.load_issues()
    aggregated_status = df.groupby([df['status']]).size().to_frame(name='count')
    _print_table(aggregated_status)

def _print_table(df):
    '''Helper to pretty print dataframes'''
    print(tabulate(df, headers='keys', tablefmt='psql'))

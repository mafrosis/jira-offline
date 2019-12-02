import datetime

import click

from jira_cli.main import Jira


@click.group()
def cli():
    '''Base CLI options'''

@cli.command(name='pull')
def cli_pull():
    '''Fetch and cache all JIRA issues'''
    dtstart = datetime.datetime.now()
    Jira.pull_issues()
    print('Query time: {}'.format(datetime.datetime.now() - dtstart))

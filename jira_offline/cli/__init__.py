'''
Application CLI entry point. Uses the click library to configure commands and subcommands, arguments,
options and help text.

This file contains the initial entry point function `cli`, and imports all commands and subcommands from
modules in the current package.
'''
from dataclasses import dataclass, field
import logging
from typing import Optional

import click

from jira_offline import __title__, __version__
from jira_offline.cli.linters import cli_lint
from jira_offline.cli.main import (cli_clone, cli_config, cli_diff, cli_edit, cli_ls, cli_new,
                                   cli_projects, cli_pull, cli_push, cli_reset, cli_show, cli_import)
from jira_offline.cli.params import global_options
from jira_offline.cli.stats import cli_stats


logger = logging.getLogger('jira')
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(sh)
logger.setLevel(logging.WARNING)


@click.group()
@click.version_option(__version__, prog_name=__title__)
@click.pass_context
@global_options
def cli(_):
    '''
    Git-like CLI for using Jira offline
    '''
    # The interesting work is actually done in the `global_options` decorator.


cli.add_command(cli_clone)
cli.add_command(cli_diff)
cli.add_command(cli_edit)
cli.add_command(cli_ls)
cli.add_command(cli_new)
cli.add_command(cli_projects)
cli.add_command(cli_config)
cli.add_command(cli_pull)
cli.add_command(cli_push)
cli.add_command(cli_reset)
cli.add_command(cli_show)
cli.add_command(cli_import)
cli.add_command(cli_lint)
cli.add_command(cli_stats)

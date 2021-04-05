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

import jira_offline
from jira_offline.cli.linters import cli_lint
from jira_offline.cli.main import (cli_clone, cli_diff, cli_edit, cli_ls, cli_new, cli_projects,
                                   cli_pull, cli_push, cli_reset, cli_show, cli_import)
from jira_offline.cli.params import CliParams
from jira_offline.cli.stats import cli_stats


logger = logging.getLogger('jira')
sh = logging.StreamHandler()
logger.addHandler(sh)
logger.setLevel(logging.ERROR)


@click.group()
@click.version_option(jira_offline.__version__, prog_name=jira_offline.__title__)
@click.option('--verbose', '-v', is_flag=True, help='Display INFO level logging')
@click.option('--debug', '-d', is_flag=True, help='Display DEBUG level logging')
@click.pass_context
def cli(ctx, verbose: bool=False, debug: bool=False):
    # setup the logger
    formatter = logging.Formatter('%(levelname)s: %(message)s')

    # handle --verbose and --debug
    if debug:
        verbose = True
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s: %(module)s:%(lineno)s - %(message)s')

    elif verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

    sh.setFormatter(formatter)

    # instantiate the Jira object for the application and wrap it into CLI params which are passed
    # down through click to the CLI function called
    ctx.obj = CliParams(verbose=verbose, debug=debug)


cli.add_command(cli_clone)
cli.add_command(cli_diff)
cli.add_command(cli_edit)
cli.add_command(cli_ls)
cli.add_command(cli_new)
cli.add_command(cli_projects)
cli.add_command(cli_pull)
cli.add_command(cli_push)
cli.add_command(cli_reset)
cli.add_command(cli_show)
cli.add_command(cli_import)
cli.add_command(cli_lint)
cli.add_command(cli_stats)

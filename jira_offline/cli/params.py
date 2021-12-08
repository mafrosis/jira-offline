'''
When a command is called on the CLI, variables and state are passed down the subcommand chain using
`@click.pass_context`. Classes defined here serve as simple DTOs to encapsulate these parameters both
globally, and for each subcommand group.

Also defined here are reuseable sets of command options, which enable common options to be mapped to
subcommands throughout the CLI (https://github.com/pallets/click/issues/108#issuecomment-280489786).
'''
from dataclasses import dataclass, field
import functools
import logging
from typing import Optional

import click
from peak.util.proxies import LazyProxy

from jira_offline.jira import jira


logger = logging.getLogger('jira')


context = LazyProxy(lambda: CliParams())  # pylint: disable=unnecessary-lambda


@dataclass
class CliParams:
    @dataclass
    class LintParams:
        '''Special params for the `jira lint` subcommand group'''
        fix: bool

    _verbose: bool = field(default=False)
    _debug: bool = field(default=False)
    debug_level: int = field(default=0)

    force: bool = field(default=False)

    lint: Optional[LintParams] = field(default=None)

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, val: bool):
        self._debug = val
        self._verbose = True
        logger.setLevel(logging.DEBUG)
        logger.handlers[0].setFormatter(logging.Formatter('%(levelname)s: %(module)s:%(lineno)s - %(message)s'))

    @property
    def verbose(self) -> bool:
        return self._verbose

    @verbose.setter
    def verbose(self, val: bool):
        self._verbose = val
        logger.setLevel(logging.INFO)


def global_options(func):
    '''
    Define a set of global CLI options which are applied to all subcommands
    '''
    @click.option('--config', '-c', type=click.Path(exists=True), help='Read configuration from PATH')
    @click.option('--verbose', '-v', is_flag=True, help='Display INFO level logging')
    @click.option('--debug', '-d', count=True, help='Display DEBUG level logging')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ctx = args[0]

        if ctx.obj is None:
            # Initialise the CliParams DTO on first call
            ctx.obj = context

        if kwargs.get('verbose'):
            ctx.obj.verbose = True
        if kwargs.get('debug'):
            ctx.obj.debug = True
            ctx.obj.debug_level = kwargs.get('debug')

        if kwargs.get('config'):
            jira.config.user_config_filepath = kwargs.get('config')

        # These options have been consumed, so remove from kwargs
        for param in ('verbose', 'debug', 'config'):
            del kwargs[param]

        return func(*args, **kwargs)

    return wrapper


def filter_option(func):
    '''
    Define a reusable --filter CLI option, which can be applied to many subcommands
    '''
    @click.option('--filter', help='SQL-like filter for issues')
    @click.option('--tz', help='Set specific timezone for date filters (default: local system timezone)')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Set the parameters directly onto the jira.filter object
        if kwargs.get('filter'):
            jira.filter.set(kwargs.get('filter'))

        if kwargs.get('tz'):
            jira.filter.tz = kwargs.get('tz')

        # These options have been consumed, so remove from kwargs
        for param in ('filter', 'tz'):
            del kwargs[param]

        return func(*args, **kwargs)

    return wrapper


def force_option(func):
    '''
    Define a reusable --force option, which can be applied to many subcommands
    '''
    @click.option('--force', '-f', is_flag=True, help='Do not prompt for confirmation. Beware!')
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ctx = args[0]

        if ctx.obj is None:
            # Initialise the CliParams DTO on first call
            ctx.obj = CliParams()

        if kwargs.get('force'):
            ctx.obj.force = True

        # This option has been consumed, so remove from kwargs
        del kwargs['force']

        return func(*args, **kwargs)

    return wrapper

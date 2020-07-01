'''
When a command is called on the CLI, variables and state are passed down the subcommand chain using
`@click.pass_context`.

Classes defined here serve as simple DTOs to encapsulate these parameters both globally, and for each
subcommand group.
'''
from dataclasses import dataclass, field
from typing import Optional

from jira_offline.jira import Jira


@dataclass
class CliParams:
    @dataclass
    class LintParams:
        '''Special params for the `jira lint` subcommand group'''
        fix: bool

    jira: Jira

    verbose: bool = field(default=False)
    debug: bool = field(default=False)

    lint: Optional[LintParams] = field(default=None)

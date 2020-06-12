from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CliParams:
    @dataclass
    class LintParams:
        fix: bool

    verbose: bool = field(default=False)
    debug: bool = field(default=False)

    lint: Optional[LintParams] = field(default=None)

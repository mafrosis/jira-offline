from typing import Tuple
import logging

import pandas as pd

from jira_cli.main import Jira


logger = logging.getLogger('jira')


def fixversions(fix: bool=False) -> Tuple[int, pd.DataFrame]:
    '''Lint on missing fixVersions field'''
    jira = Jira()
    df = jira.load_issues()

    initial_missing_count = None

    if fix:
        # count of all issues missing the fixVersions field
        initial_missing_count = len(df[df.fixVersions.apply(lambda x: len(x) == 0)])

        # set PI5/PI6 on all relevant epics
        for PI in ('PI5', 'PI6'):
            # set PI into fixVersions field on Epics if their name matches
            df[df.epic_name.str.contains(PI)].fixVersions.apply(lambda x: x.add(PI))  # pylint: disable=cell-var-from-loop

            # iterate epics
            for epic_ref in df[df.issuetype == 'Epic'].index:
                # if PI value is set in fixVersions on the epic
                if PI in jira[epic_ref].fixVersions:
                    # filter all issues under this epic, and add PI to fixVersions
                    df[df.epic_ref == jira[epic_ref].key].fixVersions.apply(
                        lambda x: x.add(PI)  # pylint: disable=cell-var-from-loop
                    )

        # Write changes to local cache
        jira.write_issues()

    # return dataframe of issues with empty fixversions field
    df_missing = df[df.fixVersions.apply(lambda x: len(x) == 0)]

    return initial_missing_count, df_missing

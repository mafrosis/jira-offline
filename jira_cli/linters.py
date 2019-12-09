import logging

import pandas as pd

from jira_cli.main import Jira


logger = logging.getLogger('jira')


def fixversions(fix: bool=False, words: list=None) -> pd.DataFrame:
    '''
    Lint on issues missing fixVersions field

    Params:
        fix     Flag to indicate if a fix should be applied
        words   Words to look for in an Epic name, and set in fixVersions
    '''
    jira = Jira()
    df = jira.load_issues()

    if fix:
        # set arbitrary fixVersion on all relevant epics
        for word in words:
            # add word to fixVersions field on Epics if their epic_name matches
            df[df.epic_name.str.contains(word)].fixVersions.apply(
                lambda x: x.add(word)  # pylint: disable=cell-var-from-loop
            )

            # iterate only epics
            for epic_ref in df[df.issuetype == 'Epic'].index:
                # if word is in fixVersions
                if word in jira[epic_ref].fixVersions:
                    # filter all issues under this epic, and add word to fixVersions
                    df[df.epic_ref == jira[epic_ref].key].fixVersions.apply(
                        lambda x: x.add(word)  # pylint: disable=cell-var-from-loop
                    )

        # write updates to disk
        jira.write_issues()

    # return dataframe of issues with empty fixversions field
    return df[df.fixVersions.apply(lambda x: len(x) == 0)]

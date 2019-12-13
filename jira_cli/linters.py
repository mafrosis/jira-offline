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
    jira.load_issues()

    if fix:
        # set arbitrary fixVersion on all relevant epics
        for word in words:
            # add word to fixVersions field on Epics if their epic_name matches
            jira.df[jira.df.epic_name.str.contains(word)].fixVersions.apply(
                lambda x: x.add(word)  # pylint: disable=cell-var-from-loop
            )

            # iterate only epics
            for epic_ref in jira.df[jira.df.issuetype == 'Epic'].index:
                # if word is in fixVersions
                if word in jira[epic_ref].fixVersions:
                    # filter all issues under this epic, and add word to fixVersions
                    jira.df[jira.df.epic_ref == jira[epic_ref].key].fixVersions.apply(
                        lambda x: x.add(word)  # pylint: disable=cell-var-from-loop
                    )

        # write updates to disk & invalidate current DataFrame representation
        jira.write_issues()
        jira.invalidate_df()

    # return dataframe of issues with empty fixversions field
    return jira.df[jira.df.fixVersions.apply(lambda x: len(x) == 0)]

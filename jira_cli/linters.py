import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    import Jira


logger = logging.getLogger('jira')


def fixversions(jira: 'Jira', fix: bool=False, words: list=None) -> pd.DataFrame:
    '''
    Lint on issues missing fixVersions field

    Params:
        jira:   Dependency-injected main.Jira object
        fix:    Flag to indicate if a fix should be applied
        words:  Words to look for in an Epic name, and set in fixVersions
    '''
    if fix and not words:
        raise Exception

    if fix:
        # set arbitrary fixVersion on all relevant epics
        for word in words:  # type: ignore
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


def issues_missing_epic(jira: 'Jira', fix: bool=False, epic_ref: str=None) -> pd.DataFrame:
    '''
    Lint issues without an epic set, default to Open issues only.

    Params:
        jira:      Dependency-injected main.Jira object
        fix:       Flag to indicate if a fix should be applied
        epic_ref:  Epic to set on issues with no epic (only applicable when fix=True)
    '''
    if fix:
        # iterate issue keys and update issue.epic_ref
        for key in jira.df[(jira.df.issuetype != 'Epic') & jira.df.epic_ref.isnull() & jira.df.is_open].index:
            jira[key].epic_ref = epic_ref

        # write updates to disk & invalidate current DataFrame representation
        jira.write_issues()
        jira.invalidate_df()

    # return dataframe of open issues missing an epic
    return jira.df[(jira.df.issuetype != 'Epic') & jira.df.epic_ref.isnull() & jira.df.is_open]

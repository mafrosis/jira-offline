import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from jira_offline.main import Jira


logger = logging.getLogger('jira')


def fixversions(jira: 'Jira', fix: bool=False, value: str=None) -> pd.DataFrame:
    '''
    Lint on issues missing fixVersions field

    Params:
        jira:   Dependency-injected main.Jira object
        fix:    Flag to indicate if a fix should be applied
        value:  Value to append to Issue's fixVersions
    '''
    if fix and not value:
        raise Exception

    if fix:
        # error handle None in epic_name field
        jira.df.epic_name.fillna(value='', inplace=True)

        # iterate only epics
        for epic_ref in jira.df[jira.df.issuetype == 'Epic'].index:
            if not jira[epic_ref].fixVersions:
                continue

            # if value is in the epic's fixVersions field
            if value in jira[epic_ref].fixVersions:
                # filter for all issues under this epic, and add value to fixVersions
                jira.df[jira.df.epic_ref == jira[epic_ref].key].fixVersions.apply(
                    lambda x: {value} if x is None else x.add(value)
                )

        # write updates to disk & invalidate current DataFrame representation
        jira.write_issues()
        jira.invalidate_df()

    # return dataframe of issues with empty fixversions field
    return jira.df[jira.df.fixVersions.apply(lambda x: x is None or len(x) == 0)]


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
        for key in jira.df[(jira.df.issuetype != 'Epic') & jira.df.epic_ref.isnull()].index:
            jira[key].epic_ref = epic_ref

        # write updates to disk & invalidate current DataFrame representation
        jira.write_issues()
        jira.invalidate_df()

    # return dataframe of open issues missing an epic
    return jira.df[(jira.df.issuetype != 'Epic') & jira.df.epic_ref.isnull()]

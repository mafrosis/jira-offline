import logging

import pandas as pd

from jira_offline.jira import jira


logger = logging.getLogger('jira')


def fix_versions(fix: bool=False, value: str=None) -> pd.DataFrame:
    '''
    Lint on issues missing fix_versions field

    Params:
        fix:    Flag to indicate if a fix should be applied
        value:  Value to append to Issue.fix_versions
    '''
    if fix and not value:
        raise Exception

    if fix:
        # error handle None in epic_name field
        jira.df.epic_name.fillna(value='', inplace=True)

        # iterate only epics
        for epic_link in jira.df[jira.df.issuetype == 'Epic'].index:
            if not jira[epic_link].fix_versions:
                continue

            # if value is in the epic's fix_versions field
            if value in jira[epic_link].fix_versions:
                # filter for all issues under this epic, and add value to fix_versions
                jira.df[jira.df.epic_link == jira[epic_link].key].fix_versions.apply(
                    lambda x: {value} if x is None else x.add(value)
                )

        # write updates to disk
        jira.write_issues()

    # return dataframe of issues with empty fixversions field
    return jira.df[jira.df.fix_versions.str.len() == 0]


def issues_missing_epic(fix: bool=False, epic_link: str=None) -> pd.DataFrame:
    '''
    Lint issues without an epic set, default to Open issues only.

    Params:
        fix:       Flag to indicate if a fix should be applied
        epic_link:  Epic to set on issues with no epic (only applicable when fix=True)
    '''
    if fix:
        # update epic_link where missing
        jira.df.loc[(jira.df.issuetype != 'Epic') & (jira.df.epic_link == ''), 'epic_link'] = epic_link

        # write updates to disk
        jira.write_issues()

    # return dataframe of open issues missing an epic
    return jira.df[(jira.df.issuetype != 'Epic') & (jira.df.epic_link == '')]

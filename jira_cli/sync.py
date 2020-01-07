import datetime
import logging

import pandas as pd
from tabulate import tabulate
from tqdm import tqdm

from jira_cli.models import Issue


CUSTOM_FIELD_EPIC_LINK = 'customfield_14182'
CUSTOM_FIELD_EPIC_NAME = 'customfield_14183'
CUSTOM_FIELD_ESTIMATE = 'customfield_10002'


logger = logging.getLogger('jira')


def pull_issues(jira: 'Jira', force: bool=False, verbose: bool=False):
    '''
    Pull changed issues from upstream Jira API

    Params:
        jira:       main.Jira object
        force:      Force reload of *all* issues, not just changed since `last_updated` value
        verbose:    Verbose print all issues as they're pulled from the API (otherwise show
                    progress bar)
    '''
    if not jira.config.projects:
        raise Exception('No projects configured, cannot continue')

    if force or jira.config.last_updated is None:
        # first/forced load; cache must be empty
        last_updated = '2010-01-01 00:00'
        logger.info('Querying for all Jira issues')
    else:
        # load existing issue data from cache
        jira.load_issues()
        last_updated = jira.config.last_updated
        logger.info('Querying for Jira issues since %s', last_updated)

    jql = f'project IN ({",".join(jira.config.projects)}) AND updated > "{last_updated}"'

    # single quick query to get total number of issues
    api = jira.connect()
    head = api.search_issues(jql, maxResults=1)

    pbar = None

    def _run(jql, pbar=None):
        page = 0
        total = 0

        while True:
            start = page * 25
            issues = api.search_issues(jql, start, 25)
            if len(issues) == 0:
                break
            page += 1
            total += len(issues)

            # add/update all issues into jira
            for issue in issues:
                jira[issue.key] = _raw_issue_to_object(issue)

            if pbar:
                # update progress
                pbar.update(len(issues))
            else:
                logger.info('Page number %s', page)
                df = pd.DataFrame.from_dict(
                    {issue.key:_raw_issue_to_object(issue).serialize() for issue in issues},
                    orient='index'
                )
                df['summary'] = df.loc[:]['summary'].str.slice(0, 100)
                print(tabulate(df[['issuetype', 'summary', 'assignee', 'updated']], headers='keys', tablefmt='psql'))

        return total

    if verbose:
        total = _run(jql)
    else:
        # show progress bar
        with tqdm(total=head.total, unit=' issues') as pbar:
            total = _run(jql, pbar)

    logger.info('Retrieved %s issues', total)

    # dump issues to JSON cache
    jira.write_issues()

    # cache the last_updated value
    jira.config.last_updated = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    jira.config.write_to_disk()


def _raw_issue_to_object(issue: dict) -> Issue:
    '''
    Convert raw JSON from JIRA API to a dataclass object
    '''
    fixVersions = set()
    if issue.fields.fixVersions:
        fixVersions = {f.name for f in issue.fields.fixVersions}

    return Issue.deserialize({
        'assignee': issue.fields.assignee.name if issue.fields.assignee else None,
        'created': issue.fields.created,
        'creator': issue.fields.creator.name,
        'epic_ref': getattr(issue.fields, CUSTOM_FIELD_EPIC_LINK),
        'epic_name': getattr(issue.fields, CUSTOM_FIELD_EPIC_NAME, ''),
        'estimate': getattr(issue.fields, CUSTOM_FIELD_ESTIMATE),
        'description': issue.fields.description,
        'fixVersions': fixVersions,
        'issuetype': issue.fields.issuetype.name,
        'key': issue.key,
        'labels': issue.fields.labels,
        'lastViewed': issue.fields.lastViewed,
        'priority': issue.fields.priority.name,
        'project': issue.fields.project.key,
        'reporter': issue.fields.reporter.name,
        'status': issue.fields.status.name,
        'summary': issue.fields.summary,
        'updated': issue.fields.updated,
    })

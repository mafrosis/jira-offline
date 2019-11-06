#! /usr/bin/env python3

# PREREQS / ASSUMPTIONS
#
# Supports only tickets from a single JIRA project
# Username/Password available for JIRA
# Must be on ANZ network to pull//push
#

from dataclasses import dataclass, field
import datetime
import json
import os
import urllib3

import click
import pandas as pd

import jira

USERNAME = ''
PASSWORD = ''
JIRA_HOSTNAME = 'https://jira.service.anz'
CUSTOM_FIELD_EPIC_LINK = 'customfield_14182'
CUSTOM_FIELD_EPIC_NAME = 'customfield_14183'
CUSTOM_FIELD_ESTIMATE = 'customfield_10002'

# pylint: disable=too-many-instance-attributes
@dataclass
class Issue:
    assignee: str
    created: str
    creator: str
    description: str
    fixVersions: list
    issuetype: str
    key: str
    labels: list
    lastViewed: str
    priority: str
    project: str
    reporter: str
    status: str
    summary: str
    updated: str
    estimate: int = field(default=None)
    epic_ref: str = field(default=None)
    epic_name: str = field(default=None)


class Jira:
    _jira = None
    _issues:dict = None

    @classmethod
    def connect(cls):
        if cls._jira:
            return cls._jira

        # no insecure cert warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        cls._jira = jira.JIRA(
            options={'server': JIRA_HOSTNAME,'verify': False},
            basic_auth=(USERNAME, PASSWORD)
        )
        return cls._jira

    @classmethod
    def pull_issues(cls):
        cls.connect()

        # load existing issue data from cache
        cls.load_issues()

        data = []
        page = 0

        while True:
            start = page * 50
            issues = cls._jira.search_issues(f'project=CNPS', start, 50)
            if len(issues) == 0:
                break
            data += issues
            page += 1

        # update changed issues
        for issue in data:
            cls._issues[issue.key] = cls._raw_issue_to_object(issue)

        # dump issues to JSON cache
        json.dump(
            {k:v.__dict__ for k,v in cls._issues.items()},
            open('issue_cache.json', 'w')
        )
        return cls._issues

    @classmethod
    def _raw_issue_to_object(cls, issue):
        """
        Convert raw JSON from JIRA API to a dataclass object
        """
        fixVersions = []
        if issue.fields.fixVersions:
            fixVersions = [f.name for f in issue.fields.fixVersions]

        return Issue(**{
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

    @classmethod
    def load_issues(cls) -> pd.DataFrame:
        """
        Load issues from JSON cache file, and store as class variable
        return DataFrame of entire dataset
        """
        if not os.path.exists('issue_cache.json'):
            # first run; cache file doesn't exist
            cls._issues = cls.pull_issues()
        else:
            # load from cache file
            cls._issues = {
                k:Issue(**v)
                for k,v in json.load(open('issue_cache.json')).items()
            }

        return Jira.to_frame()

    @classmethod
    def to_frame(cls):
        """
        Convert class variable to pandas DataFrame
        """
        df = pd.DataFrame.from_dict(
            {key: issue.__dict__ for key, issue in cls._issues.items()}, orient='index'
        )
        df = df[ (df.issuetype != 'Delivery Risk') & (df.issuetype != 'Ops/Introduced Risk') ]
        return df


@click.group()
def cli():
    '''Base CLI options'''

@cli.command(name='pull')
def cli_pull():
    '''Fetch and cache all JIRA issues'''
    dtstart = datetime.datetime.now()
    Jira.pull_issues()
    print('Query time: {}'.format(datetime.datetime.now() - dtstart))


if __name__ == '__main__':
    cli()

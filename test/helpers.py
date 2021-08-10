from typing import List

import pandas as pd

from jira_offline.models import Issue


def compare_issue_helper(issue, compare_issue):
    'Helper to compare two issues with assertions'
    assert isinstance(compare_issue, Issue)
    assert issue.project == compare_issue.project
    assert issue.project_id == compare_issue.project_id
    assert issue.issuetype == compare_issue.issuetype
    assert issue.summary == compare_issue.summary
    assert issue.assignee == compare_issue.assignee
    assert issue.created == compare_issue.created
    assert issue.creator == compare_issue.creator
    assert issue.epic_name is None and compare_issue.epic_name == '' or \
            issue.epic_name == compare_issue.epic_name
    assert issue.epic_ref is None and compare_issue.epic_ref == '' or \
            issue.epic_ref == compare_issue.epic_ref
    assert issue.sprint is None and compare_issue.sprint == '' or \
            issue.sprint == compare_issue.sprint
    assert issue.story_points is None and compare_issue.story_points == '' or \
            issue.story_points == compare_issue.story_points
    assert issue.extended is None and compare_issue.extended == {} or \
            issue.extended == compare_issue.extended
    assert issue.description == compare_issue.description
    assert issue.fix_versions == set(compare_issue.fix_versions)
    assert issue.components == set(compare_issue.components)
    assert issue.id == compare_issue.id
    assert issue.key == compare_issue.key
    assert issue.labels == set(compare_issue.labels)
    assert issue.priority == compare_issue.priority
    assert issue.reporter == compare_issue.reporter
    assert issue.status == compare_issue.status
    assert issue.updated == compare_issue.updated
    assert issue.original == compare_issue.original


def setup_jira_dataframe_helper(issues: List[Issue]):
    'Helper to ensure the Jira DataFrame is setup correctly'
    df = pd.concat(
        [issue.to_series() for issue in issues],
        axis=1,
        keys=[i.key for i in issues]
    ).T

    df = df.fillna('').convert_dtypes()

    # convert all datetimes to UTC, where they are non-null (this is all non-new issues)
    for col in ('created', 'updated'):
        df[col] = df[col].dt.tz_convert('UTC')

    return df

'''
Helpers for writing easy-to-read unit tests
'''
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
    assert issue.epic_link is None and compare_issue.epic_link == '' or \
            issue.epic_link == compare_issue.epic_link
    assert issue.sprint is None and compare_issue.sprint == '' or \
            issue.sprint == compare_issue.sprint
    assert issue.story_points is None and compare_issue.story_points == '' or \
            issue.story_points == compare_issue.story_points
    assert issue.parent_link is None and compare_issue.parent_link == '' or \
            issue.parent_link == compare_issue.parent_link
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


def modified_issue_helper(issue, **kwargs):
    'Helper to modify fixture issues in the correct way'
    for k, v in kwargs.items():
        setattr(issue, k, v)

    # Ensure the issue has its diff created correctly
    issue.diff()
    return issue

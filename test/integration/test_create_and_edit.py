'''
End-to-end integration tests which use a real instance of Jira

These tests concern editing fields offline and pushing to Jira
'''
import json

import pytest


@pytest.mark.integration
def test_create_new_issue_and_edit_before_push(jira_project, run_in_docker):
    '''
    Ensure Story can be created, and subsequently edited before a push
    '''
    # create a new issue
    output = run_in_docker(jira_project, f'new --json {jira_project} Story EGGpic')

    # parse new issue created (printed on stdout with --json)
    data = json.loads(output)

    # edit the issue
    run_in_docker(jira_project, f'edit {data["key"]} --labels=egg,bacon')

    # push to Jira
    output = run_in_docker(jira_project, '--verbose push')
    assert 'INFO: Pushed 1 of 1 issues' in output

    # load and parse all current issues (there will be only 1!)
    output = run_in_docker(jira_project, f'ls --json')
    data = json.loads(output)

    # ensure edit we successful
    assert 'egg' in data['labels'] and 'bacon' in data['labels']


@pytest.mark.integration
def test_edit_existing_issue_and_push(jira_project, run_in_docker):
    '''
    Ensure existing Story can be edited, and then pushed successfully
    '''
    def setup():
        # create a new issue
        output = run_in_docker(jira_project, f'new --json {jira_project} Story EGGpic')

        # push to Jira
        output = run_in_docker(jira_project, '--verbose push')
        assert 'INFO: Pushed 1 of 1 issues' in output

    # setup Jira for test
    setup()

    # load and parse all current issues (there will be only 1!)
    output = run_in_docker(jira_project, f'ls --json')
    data = json.loads(output)

    # edit the issue
    run_in_docker(jira_project, f'edit {data["key"]} --labels=egg,bacon')

    # push to Jira
    output = run_in_docker(jira_project, '--verbose push')
    assert 'INFO: Pushed 1 of 1 issues' in output

    # load and parse all current issues (there will be only 1!)
    output = run_in_docker(jira_project, f'ls --json')
    data = json.loads(output)

    # ensure edit was successful
    assert 'egg' in data['labels'] and 'bacon' in data['labels']

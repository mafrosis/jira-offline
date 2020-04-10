'''
End-to-end integration tests which use a real instance of Jira
'''
import pytest


@pytest.mark.integration
def test_push_epics_with_issues_created_offline(jira_project, run_in_docker):
    '''
    Ensure offline creation of epic and linked issue push to Jira correctly
    '''
    run_in_docker(jira_project, f'new {jira_project} Epic EGGpic --epic-name EGGpic')
    run_in_docker(jira_project, f'new {jira_project} Story stozza1 --epic-ref EGGpic')
    run_in_docker(jira_project, f'new {jira_project} Epic EGGpic2 --epic-name EGGpic2')

    output = run_in_docker(jira_project, '--verbose push')

    assert 'INFO: Pushed 3 of 3 issues' in output

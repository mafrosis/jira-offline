'''
End-to-end integration tests which use a real instance of Jira.

These tests concern pushing multiple new issues to Jira at once.
'''
import pytest


@pytest.mark.integration
def test_push__create_with_epic_link(jira_project, run_in_docker):
    '''
    Ensure story can be created linked to an epic, and subsequently pushed
    '''
    run_in_docker(jira_project, f'new {jira_project} Epic Epic1 --epic-name Epic1')
    run_in_docker(jira_project, f'new {jira_project} Story Story1 --epic-link Epic1')
    run_in_docker(jira_project, f'new {jira_project} Epic Epic2 --epic-name Epic2')

    output = run_in_docker(jira_project, '--verbose push')

    assert 'Pushed 3 of 3 issues' in output


#@pytest.mark.integration
#def test_push__create_and_then_link_after(jira_project, run_in_docker):
#    '''
#    Ensure story and epic can be linked, and subsequently pushed
#    '''
#    output = run_in_docker(jira_project, f'new {jira_project} Story stozza1')
#    import ipdb; ipdb.set_trace()
#    run_in_docker(jira_project, f'new {jira_project} Epic EGGpic --epic-name EGGpic')
#    run_in_docker(jira_project, f'edit {story_uuid} --epic-link EGGpic')
#
#    output = run_in_docker(jira_project, '--verbose push')
#
#    assert 'INFO: Pushed 3 of 3 issues' in output

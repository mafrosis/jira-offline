'''
Tests for the Jira API class in main.py

Unlike other tests, these access the class directly, not via the mock_jira interface defined in
conftest.py
'''
from jira_cli.models import ProjectMeta


def test_jira__get_project_meta__extracts_issuetypes(mock_jira_core):
    '''
    Ensure get_project_meta() method parses the issuetypes for a project
    '''
    # mock return from Jira createmeta API call
    mock_jira_core._jira.createmeta.return_value = {
        'projects': [{
            'id': '56120',
            'key': 'EGG',
            'name': 'Project EGG',
            'issuetypes': [{
                'id': '5',
                'name': 'Epic',
                'fields': {},
            },{
                'id': '18500',
                'name': 'Party',
                'fields': {},
            }]
        }]
    }
    result = mock_jira_core.get_project_meta('EGG')

    assert mock_jira_core.connect.called
    assert mock_jira_core._jira.createmeta.called
    assert result == ProjectMeta(name='Project EGG', issuetypes={'Epic', 'Party'})

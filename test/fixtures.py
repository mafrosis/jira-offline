ISSUE_1 = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'assignee': 'danil1',
    'created': '2018-09-24T08:44:06',
    'creator': 'danil1',
    'description': 'This is a story or issue',
    'fix_versions': ['0.1'],
    'issuetype': 'Story',
    'id': '1231',
    'key': 'TEST-71',
    'labels': [],
    'components': [],
    'priority': 'Normal',
    'reporter': 'danil1',
    'status': 'Story Done',
    'summary': 'This is the story summary',
    'updated': '2019-08-20T16:41:19',
    'epic_link': 'TEST-1',
    'story_points': '1',
    'diff_to_original': [],
}

ISSUE_NEW = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'key': '7242cc9e-ea52-4e51-bd84-2ced250cabf0',
    'description': 'This is a story or issue',
    'issuetype': 'Story',
    'reporter': 'danil1',
    'summary': 'This is the story summary',
    'epic_link': 'TEST-1',
    'fix_versions': ['0.1'],
}

EPIC_1 = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'created': '2018-09-24T08:44:06',
    'creator': 'danil1',
    'fix_versions': ['0.1'],
    'issuetype': 'Epic',
    'id': '2345',
    'key': 'TEST-1',
    'reporter': 'danil1',
    'status': 'Epic with Squad',
    'summary': 'This is an epic',
    'updated': '2019-08-27T16:41:19',
    'epic_name': '0.1: Epic about a thing',
    'diff_to_original': [],
}

EPIC_NEW = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'key': '9fb9e0f9-6c0c-4d9d-a8b4-6e19a378275c',
    'summary': 'This is an epic',
    'epic_name': '0.1: Epic about a thing',
    'issuetype': 'Epic',
    'reporter': 'danil1',
}

# A fixture representing the struct returned by the Jira API
JIRAAPI_OBJECT = {
    'fields': {
        'assignee': {'displayName': ISSUE_1['assignee']},
        'components': [],
        'created': ISSUE_1['created'],
        'creator': {'displayName': ISSUE_1['creator']},
        'description': ISSUE_1['description'],
        'fixVersions': [],
        'issuetype': {'name': ISSUE_1['issuetype']},
        'labels': [],
        'priority': {'name': ISSUE_1['priority']},
        'project_id': 'TEST',
        'reporter': {'displayName': ISSUE_1['reporter']},
        'status': {'name': ISSUE_1['status']},
        'summary': ISSUE_1['summary'],
        'updated': ISSUE_1['updated'],
        'customfield_10100': ISSUE_1['epic_link'],
    },
    'id': ISSUE_1['id'],
    'key': ISSUE_1['key'],
}

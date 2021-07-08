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
    'epic_ref': 'TEST-1',
    'story_points': '1',
    'diff_to_original': [],
    'modified': False,
}

ISSUE_1_WITH_UPDATED_DIFF = {
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
    'updated': '2000-08-21T00:00:00',
    'epic_ref': 'TEST-1',
    'story_points': '1',
    'diff_to_original': [('change', 'updated', ('2000-08-20T00:00:00', '2019-08-20T16:41:19'))],
    'modified': True,
}

ISSUE_1_WITH_ASSIGNEE_DIFF = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'assignee': 'hoganp',
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
    'updated': '2019-08-23T16:41:19',
    'epic_ref': 'TEST-1',
    'story_points': '1',
    'diff_to_original': [('change', 'assignee', ('hoganp', 'danil1'))],
    'modified': True,
}

ISSUE_1_WITH_FIXVERSIONS_DIFF = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'assignee': 'danil1',
    'created': '2018-09-24T08:44:06',
    'creator': 'danil1',
    'description': 'This is a story or issue',
    'fix_versions': ['0.1', '0.2'],
    'issuetype': 'Story',
    'id': '1231',
    'key': 'TEST-71',
    'labels': [],
    'components': [],
    'priority': 'Normal',
    'reporter': 'danil1',
    'status': 'Story Done',
    'summary': 'This is the story summary',
    'updated': '2019-08-24T16:41:19',
    'epic_ref': 'TEST-1',
    'story_points': '1',
    'diff_to_original': [('remove', 'fix_versions', [(1, '0.2')])],
    'modified': True,
}

ISSUE_2 = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'assignee': 'danil1',
    'created': '2018-09-24T08:44:06',
    'creator': 'danil1',
    'description': 'This is a story or issue',
    'fix_versions': [],
    'issuetype': 'Story',
    'id': '1235',
    'key': 'TEST-72',
    'labels': ['egg', 'bacon'],
    'components': [],
    'priority': 'Normal',
    'reporter': 'danil1',
    'status': 'Backlog',
    'summary': 'This is the story summary',
    'updated': '2019-08-25T16:41:19',
    'epic_ref': 'TEST-1',
    'diff_to_original': [],
    'modified': False,
}

ISSUE_MISSING_EPIC = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'created': '2018-09-24T08:44:06',
    'creator': 'danil1',
    'description': 'This is a story or issue',
    'fix_versions': [],
    'issuetype': 'Story',
    'id': '1236',
    'key': 'TEST-73',
    'labels': [],
    'components': [],
    'priority': 'Normal',
    'reporter': 'danil1',
    'status': 'Backlog',
    'summary': 'This is the story summary',
    'updated': '2019-08-20T16:41:19',
    'story_points': '1.5',
    'diff_to_original': [],
    'modified': False,
}

ISSUE_NEW = {
    'project_id': '99fd9182cfc4c701a8a662f6293f4136201791b4',
    'key': '7242cc9e-ea52-4e51-bd84-2ced250cabf0',
    'description': 'This is a story or issue',
    'issuetype': 'Story',
    'reporter': 'danil1',
    'summary': 'This is the story summary',
    'epic_ref': 'TEST-1',
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
    'modified': False,
}

ISSUE_DIFF_PROJECT = {
    'project_id': 'ae7da7e6f3199b1f10e0c4ecfa54ce52158da4db',
    'assignee': 'bea1',
    'created': '2018-09-24T08:44:06',
    'creator': 'bea1',
    'description': 'This is a story or issue',
    'fix_versions': [],
    'issuetype': 'Story',
    'id': '99',
    'key': 'EGG-99',
    'labels': [],
    'components': [],
    'priority': 'Normal',
    'reporter': 'danil1',
    'status': 'Backlog',
    'summary': 'This is the story summary',
    'updated': '2019-08-28T16:41:19',
    'diff_to_original': []
}

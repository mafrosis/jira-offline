import random
import string
import tempfile
from unittest import mock

from requests.auth import HTTPBasicAuth
import requests
import docker
import pytest
import pytz

from tzlocal import get_localzone

from jira_offline.jira import Jira
from jira_offline.models import AppConfig, CustomFields, IssueType, ProjectMeta


@pytest.fixture(params=['customfield_10100', ''])
def customfield_estimate(request):
    '''Parameterized fixture to feed the project fixture below'''
    return request.param


@pytest.fixture(params=[
    ['High', 'Low'],
    [],
])
def customfield_priority(request):
    '''Parameterized fixture to feed the project fixture below'''
    return set(request.param)


@pytest.fixture(params=[get_localzone(), pytz.timezone('Europe/London')])
def timezone(request):
    '''Parameterized fixture to feed the project fixture below'''
    return request.param


@pytest.fixture
def project(customfield_estimate, customfield_priority, timezone):
    '''
    Fixture representing a configured Jira project
    '''
    return ProjectMeta(
        key='TEST',
        username='test',
        password='dummy',
        custom_fields=CustomFields(epic_ref='1', epic_name='2', estimate=customfield_estimate),
        priorities=customfield_priority,
        timezone=timezone,
        issuetypes={
            'Story': IssueType(name='Story', statuses=['Backlog', 'Done']),
        },
    )


@pytest.fixture
@mock.patch('jira_offline.jira.load_config')
def mock_jira_core(mock_load_config, project):
    '''
    Return a Jira class instance with connect method and underlying Jira lib mocked
    '''
    jira = Jira()
    jira.config = AppConfig(projects={project.id: project})
    # ensure each ProjectMeta instance has a reference to the AppConfig instance
    # in normal operation, this is done in `load_config` in config.py, and so applies to all projects
    project.config = jira.config
    # never write to disk during tests
    jira.config.write_to_disk = mock.Mock()
    return jira


@pytest.fixture
def mock_jira(mock_jira_core):
    '''
    Mock additional methods of Jira class
    '''
    mock_jira_core.load_issues = mock.Mock()
    mock_jira_core.write_issues = mock.Mock()
    mock_jira_core.update_issue = mock.Mock()
    mock_jira_core.new_issue = mock.Mock()
    mock_jira_core.fetch_issue = mock.Mock()
    mock_jira_core.get_project_meta = mock.Mock()
    return mock_jira_core


def pytest_addoption(parser):
    '''
    Add extra parameters to pytest for integration tests
    '''
    parser.addoption('--hostname', action='store')
    parser.addoption('--username', action='store')
    parser.addoption('--password', action='store')
    parser.addoption('--cwd', action='store')


@pytest.fixture
def jira_project(request, run_in_docker):
    '''
    Create a new Jira project on a real instance of Jira, using supplied parameters.

    Yield the newly created project's ID for integration testing, and then cleanup the project when
    finished.
    '''
    hostname = request.config.getoption('--hostname')
    username = request.config.getoption('--username')
    password = request.config.getoption('--password')
    cwd = request.config.getoption('--cwd')

    if not hostname or not username or not password or not cwd:
        raise Exception(
            'pytest: error the following arguments are required: --username, --hostname, --password, --cwd'
        )

    # create random 8 char uppercase string
    project_key = ''.join(random.choice(string.ascii_uppercase) for _ in range(8))

    # create new project in Jira
    resp = requests.post(
        f'http://{hostname}/rest/api/2/project',
        auth=HTTPBasicAuth(username, password),
        json={
            'key': project_key,
            'lead': 'blackm',
            'name': project_key,
            'projectTypeKey': 'software',
            'projectTemplateKey': 'com.pyxis.greenhopper.jira:gh-scrum-template',
        },
    )
    if resp.status_code > 205:
        raise Exception('{} {}'.format(resp.status_code, resp.text))

    # fetch screens for this new project
    resp = requests.get(
        f'http://{hostname}/rest/api/2/screens',
        auth=HTTPBasicAuth(username, password),
    )
    screen_ids = [x['id'] for x in resp.json() if x['name'][0:8] == project_key]

    # retrieve the screen's "availableFields", to find the id of the "Story Points" custom field
    resp = requests.get(
        f'http://{hostname}/rest/api/2/screens/{screen_ids[0]}/availableFields',
        auth=HTTPBasicAuth(username, password),
    )
    estimate_customfield_id = [x['id'] for x in resp.json() if x['name'] == 'Story Points'][0]

    # add "Story Points" (aka Issue.estimate) to every screen in the project
    for screen_id in screen_ids:
        # iterate the screen's tabs (there should be only 1 for a new project)
        resp = requests.get(
            f'http://{hostname}/rest/api/2/screens/{screen_id}/tabs',
            auth=HTTPBasicAuth(username, password),
        )
        for tab_id in [x['id'] for x in resp.json()]:
            resp = requests.post(
                f'http://{hostname}/rest/api/2/screens/{screen_id}/tabs/{tab_id}/fields',
                auth=HTTPBasicAuth(username, password),
                json={
                    'fieldId': estimate_customfield_id,
                },
            )

    # clone the new project
    run_in_docker(
        project_key,
        f'clone --username {username} --password {password} http://{hostname}/{project_key}'
    )
    yield project_key

    # delete the Jira test project
    resp = requests.delete(
        f'http://{hostname}/rest/api/2/project/{project_key}',
        auth=HTTPBasicAuth(username, password),
    )


@pytest.fixture
def run_in_docker(request):
    '''
    Run a command in docker during an integration test run
    '''
    cwd = request.config.getoption('--cwd')
    if not cwd:
        raise Exception(
            'pytest: error the following arguments are required: --username, --hostname, --password, --cwd'
        )

    tmpdir = tempfile.TemporaryDirectory()
    print(f'Test working directory {tmpdir.name}')

    client = docker.from_env()

    def wrapped(project_key: str, cmd: str):
        try:
            stdout = client.containers.run(
                'mafrosis/jira-offline',
                command=cmd,
                remove=True,
                stderr=True,
                mounts=[
                    docker.types.Mount(type='bind', source=f'{cwd}/jira_offline', target='/app/jira_offline', read_only=True),
                    docker.types.Mount(type='bind', source=tmpdir.name, target='/root/.config/jira-offline'),
                ],
            )
            # containers.run returns bytes, so encode, print and return
            ret = stdout.decode('utf8')
            print(ret)
            return ret

        except docker.errors.ContainerError as e:
            raise Exception(f'Docker run failed during integration test ({e})') from e

    yield wrapped
    tmpdir.cleanup()

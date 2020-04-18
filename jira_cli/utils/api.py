import json
import logging
from typing import Any, Dict, Optional

import requests

from jira_cli.exceptions import JiraApiError
from jira_cli.models import ProjectMeta


logger = logging.getLogger('jira')


def _request(method: str, project: ProjectMeta, path: str, params: Optional[Dict[str, Any]]=None,
             data: Optional[Dict[str, Any]]=None) -> dict:
    '''
    Make an authenticated HTTP request to the Jira API

    Params:
        project:  Configured Jira project instance to call
        path:     API path to call
        params:   Key/value of parameters to send in request URL
        data:     Key/value of parameters to send as JSON in request body
    '''
    logger.debug('%s %s/rest/api/2/%s %s', method, project.jira_server, path, json.dumps(data))
    resp = requests.request(
        method, f'{project.jira_server}/rest/api/2/{path}',
        json=data,
        params=params,
        auth=project.oauth,
    )

    if resp.status_code != 200:
        raise JiraApiError(
            f'HTTP {resp.status_code} returned from {method} /rest/api/2/{path}',
            inner_message=resp.json()['errorMessages'][0]
        )
    return resp.json()


def get(project: ProjectMeta, path: str, params: Optional[Dict[str, Any]]=None) -> dict:
    '''
    Make an authenticated GET request to the Jira API

    Params:
        project:  Configured Jira project instance to call
        path:     API path to call
        params:   Key/value of parameters to send in request URL
    '''
    return _request('GET', project, path, params=params)


def post(project: ProjectMeta, path: str, data: Optional[Dict[str, Any]]=None) -> dict:
    '''
    Make an authenticated POST request to the Jira API

    Params:
        project:  Configured Jira project instance to call
        path:     API path to call
        data:     Key/value of parameters to send as JSON in request body
    '''
    return _request('POST', project, path, data=data)


def put(project: ProjectMeta, path: str, data: Dict[str, Any]) -> dict:
    '''
    Make an authenticated PUT request to the Jira API

    Params:
        project:  Configured Jira project instance to call
        path:     API path to call
        data:     Key/value of parameters to send as JSON in request body
    '''
    return _request('PUT', project, path, data=data)

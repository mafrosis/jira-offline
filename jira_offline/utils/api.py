'''
Utility functions for talking to Jira API
'''
import json
import logging
from typing import Any, Dict, Optional

import requests

from jira_offline.exceptions import JiraApiError, JiraUnavailable
from jira_offline.models import ProjectMeta


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
    try:
        resp = requests.request(
            method, f'{project.jira_server}/rest/api/2/{path}',
            json=data,
            params=params,
            auth=project.auth,
            verify=project.ca_cert if project.ca_cert else True,
        )
        # log the entire HTTP request for debug mode
        logger.debug(30 * '-')
        logger.debug('%s %s/rest/api/2/%s', method, project.jira_server, path)
        logger.debug('\n'.join([f'{k}: {v}' for k,v in resp.request.headers.items()]))
        logger.debug('')
        logger.debug(json.dumps(data))
        logger.debug('')
        logger.debug('%s %s/rest/api/2/%s %s', method, project.jira_server, path, resp.status_code)
        logger.debug('\n'.join([f'{k}: {v}' for k,v in resp.headers.items()]))
        logger.debug('')
        logger.debug(resp.text)
        logger.debug(30 * '-')

        # raise an exception for non-200 range response
        resp.raise_for_status()

    except requests.exceptions.HTTPError:
        if resp.status_code >= 400:
            msg = f'HTTP {resp.status_code} returned from {method} /rest/api/2/{path}'

            inner_message = None
            try:
                inner_message = resp.json().get('errorMessages')
            except json.decoder.JSONDecodeError:
                pass
            raise JiraApiError(msg, inner_message=inner_message)

    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        raise JiraUnavailable(e)

    try:
        return resp.json()
    except json.decoder.JSONDecodeError:
        return {}


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


def head(project: ProjectMeta, path: str) -> dict:
    '''
    Make an authenticated head request to the Jira API

    Params:
        project:  Configured Jira project instance to call
        path:     API path to call
    '''
    return _request('HEAD', project, path)

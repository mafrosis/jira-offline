'''
This module contains functions for authenticating a user against a Jira server
'''
from typing import Optional
from urllib.parse import parse_qsl
import webbrowser

import click
from oauthlib.oauth1 import SIGNATURE_RSA
import requests
import requests_oauthlib
from requests_oauthlib.oauth1_session import TokenRequestDenied

from jira_offline import __title__
from jira_offline.exceptions import FailedAuthError, JiraApiError, JiraUnavailable, NoAuthenticationMethod
from jira_offline.models import ProjectMeta, OAuth
from jira_offline.utils.api import head as api_head


def authenticate(project: ProjectMeta, username: Optional[str]=None, password: Optional[str]=None,
                 oauth_consumer_key: Optional[str]=None, oauth_private_key_path: Optional[str]=None):
    '''
    Authenticate against hostname with either basic-auth or oAuth

    Params:
        project:                 Properties of the project we're authenticating against
        username:                Basic auth username
        oauth_consumer_key:      oAuth1 consumer key defined on the Jira Application Link
        oauth_private_key_path:  Path to the oAuth1 private key file
    '''
    if oauth_consumer_key and oauth_private_key_path:
        with open(oauth_private_key_path) as f:
            # do the oAuth1 dance
            oauth_dance(project, oauth_consumer_key, f.read())

    elif username:
        # ask for password and validate creds
        get_user_creds(project, username, password)

    else:
        raise NoAuthenticationMethod


def get_user_creds(project: ProjectMeta, username: Optional[str]=None, password: Optional[str]=None):
    '''
    Accept username/password and validate against Jira server

    Params:
        project:   Properties of the project we're authenticating against
        username:  Basic auth username
        password:  Basic auth password
    '''
    project.username = username
    if not project.username:
        project.username = click.prompt('Username', type=str)

    project.password = password
    if not project.password:
        project.password = click.prompt('Password', type=str, hide_input=True)

    # validate Jira connection details
    if project.username and project.password:
        if not _test_jira_connect(project):
            raise FailedAuthError(project.hostname)


def _test_jira_connect(project: ProjectMeta) -> bool:
    '''
    Test connection to Jira API to validate config object credentials

    Params:
        project:  Properties of the project we're authenticating against
    '''
    try:
        api_head(project, 'mypermissions')
        return True
    except JiraApiError:
        return False


def oauth_dance(project: ProjectMeta, consumer_key: str, key_cert_data: str, verify: Optional[bool]=None):
    '''
    Do the oAuth1 flow with the configured Jira Application Link.

    https://requests-oauthlib.readthedocs.io/en/latest/oauth1_workflow.html

    Params:
        project:        Properties of the project we're authenticating against
        consumer_key:   ooAuth1 consumer key defined on the Jira Application Link
        key_cert_data:  oAuth1 private key data
    '''
    if verify is None:
        verify = project.protocol == 'https'

    jira_url = f'{project.protocol}://{project.hostname}'

    # step 1: get request tokens
    oauth_session = requests_oauthlib.OAuth1Session(
        consumer_key, signature_method=SIGNATURE_RSA, rsa_key=key_cert_data
    )
    try:
        token_data = oauth_session.fetch_request_token(f'{jira_url}/plugins/servlet/oauth/request-token')
    except requests.exceptions.ConnectionError as e:
        raise JiraUnavailable
    except (TokenRequestDenied, ValueError) as e:
        raise FailedAuthError(e)

    # step 2: prompt user to validate
    auth_url = f'{jira_url}/plugins/servlet/oauth/authorize?oauth_token={token_data["oauth_token"]}'

    webbrowser.open_new(auth_url)

    click.echo(f'\nPlease visit this URL to authorize jira-offline to access your data:\n    {auth_url}\n')
    click.confirm(f'Have you authorized this program to connect on your behalf to {jira_url}?', abort=True)

    # step 3: get access tokens for validated user
    oauth = requests_oauthlib.OAuth1(
        consumer_key,
        signature_method=SIGNATURE_RSA,
        rsa_key=key_cert_data,
        resource_owner_key=token_data['oauth_token'],
        resource_owner_secret=token_data['oauth_token_secret'],
    )
    resp = requests.post(f'{jira_url}/plugins/servlet/oauth/access-token', verify=verify, auth=oauth)
    if resp.status_code != 200:
        raise FailedAuthError

    access = dict(parse_qsl(resp.text))

    # cache the oauth data for the project
    project.oauth = OAuth.deserialize({
        'access_token': access['oauth_token'],
        'access_token_secret': access['oauth_token_secret'],
        'consumer_key': consumer_key,
        'key_cert': key_cert_data,
    })

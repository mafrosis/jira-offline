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

from jira_cli import __title__
from jira_cli.exceptions import FailedAuthError, JiraUnavailable
from jira_cli.models import AppConfig, OAuth


def authenticate(config: AppConfig, protocol: str, hostname: str, username: Optional[str]=None,
                 oauth_consumer_key: Optional[str]=None, oauth_private_key_path: Optional[str]=None):
    '''
    Authenticate against hostname with either basic-auth or oAuth

    Params:
        config:                  Dependency-injected application config object
        protocol:                Protocol to use connecting to Jira (http/https)
        hostname:                Hostname of the Jira server (including port if non-standard)
        username:                Basic auth username
        oauth_consumer_key:      oAuth1 consumer key defined on the Jira Application Link
        oauth_private_key_path:  Path to the oAuth1 private key file
    '''
    # store the Jira server protocol and hostname
    config.protocol = protocol
    config.hostname = hostname

    if oauth_consumer_key and oauth_private_key_path:
        with open(oauth_private_key_path) as f:
            # do the oAuth1 dance
            oauth_dict = oauth_dance(f'{protocol}://{hostname}', oauth_consumer_key, f.read())
            config.oauth = OAuth.deserialize(oauth_dict)

    elif username:
        # ask for password and validate creds
        get_user_creds(config, username)

    # on successful authentication to Jira API; write config to local file
    config.write_to_disk()


def get_user_creds(config: AppConfig, username: Optional[str]=None):
    '''
    Accept username/password and validate against Jira server

    Params:
        config:    Dependency-injected application config object
        username:  Basic auth username
    '''
    config.username = username
    if not config.username:
        config.username = click.prompt('Username', type=str)

    config.password = click.prompt('Password', type=str, hide_input=True)

    # validate Jira connection details
    if config.username and config.password:
        if not _test_jira_connect(config):
            raise FailedAuthError(config.hostname)


def _test_jira_connect(config: AppConfig):
    '''Test connection to Jira API to validate config object credentials'''
    try:
        # late import of Jira class to prevent cyclic-import
        from jira_cli.main import Jira  # pylint: disable=import-outside-toplevel,cyclic-import
        Jira().connect(config)
        return True
    except requests.exceptions.ConnectionError:
        return False


def oauth_dance(jira_url: str, consumer_key: str, key_cert_data: str, verify: Optional[bool]=None):
    '''
    Do the oAuth1 flow with the configured Jira Application Link.

    Copied from pycontribs/jira

    Params:
        jira_url:       Jira server URL to connect to
        consumer_key:   ooAuth1 consumer key defined on the Jira Application Link
        key_cert_data:  oAuth1 private key data
    '''
    if verify is None:
        verify = jira_url.startswith('https')

    # step 1: get request tokens
    oauth = requests_oauthlib.OAuth1(consumer_key, signature_method=SIGNATURE_RSA, rsa_key=key_cert_data)
    resp = requests.post(
        f'{jira_url}/plugins/servlet/oauth/request-token', verify=verify, auth=oauth
    )
    if resp.status_code != 200:
        raise JiraUnavailable

    request = dict(parse_qsl(resp.text))
    if request.get('oauth_problem'):
        raise FailedAuthError(request['oauth_problem'])

    # step 2: prompt user to validate
    auth_url = f'{jira_url}/plugins/servlet/oauth/authorize?oauth_token={request["oauth_token"]}'

    webbrowser.open_new(auth_url)

    click.echo(f'\nPlease visit this URL to authorize jiracli to access your data:\n    {auth_url}\n')
    click.confirm(f'Have you authorized this program to connect on your behalf to {jira_url}?', abort=True)

    # step 3: get access tokens for validated user
    oauth = requests_oauthlib.OAuth1(
        consumer_key,
        signature_method=SIGNATURE_RSA,
        rsa_key=key_cert_data,
        resource_owner_key=request['oauth_token'],
        resource_owner_secret=request['oauth_token_secret'],
    )
    resp = requests.post(f'{jira_url}/plugins/servlet/oauth/access-token', verify=verify, auth=oauth)
    if resp.status_code != 200:
        raise FailedAuthError

    access = dict(parse_qsl(resp.text))

    return {
        'access_token': access['oauth_token'],
        'access_token_secret': access['oauth_token_secret'],
        'consumer_key': consumer_key,
        'key_cert': key_cert_data,
    }

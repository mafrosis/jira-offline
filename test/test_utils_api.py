from unittest import mock

from jira_offline.utils.api import _request, head, get, post, put


@mock.patch('jira_offline.utils.api.requests')
def test_requests__calls_requests_request(mock_requests, project):
    '''
    Dumb test ensuring we call requests.request, and then call response.json()
    '''
    mock_requests.request.return_value = mock_response = mock.MagicMock()
    mock_response.status_code = 200

    _request('GET', project, 'path/')

    assert mock_requests.request.called
    assert mock_response.json.called


@mock.patch('jira_offline.utils.api._request')
def test_get__calls_request_with_get_http_method(mock_request_func, project):
    '''
    Ensure get() calls _request with param "GET"
    '''
    get(project, 'path/', params={'egg': 'bacon'})

    mock_request_func.assert_called_with('GET', project, 'path/', params={'egg': 'bacon'})


@mock.patch('jira_offline.utils.api._request')
def test_post__calls_request_with_post_http_method(mock_request_func, project):
    '''
    Ensure post() calls _request with param "POST"
    '''
    post(project, 'path/', data={'egg': 'bacon'})

    mock_request_func.assert_called_with('POST', project, 'path/', data={'egg': 'bacon'})


@mock.patch('jira_offline.utils.api._request')
def test_put__calls_request_with_put_http_method(mock_request_func, project):
    '''
    Ensure put() calls _request with param "PUT"
    '''
    put(project, 'path/', data={'egg': 'bacon'})

    mock_request_func.assert_called_with('PUT', project, 'path/', data={'egg': 'bacon'})


@mock.patch('jira_offline.utils.api._request')
def test_head__calls_request_with_head_http_method(mock_request_func, project):
    '''
    Ensure head() calls _request with param "HEAD"
    '''
    head(project, 'path/')

    mock_request_func.assert_called_with('HEAD', project, 'path/')

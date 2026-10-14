"""Refresh failures preserve tokens and distinguish outages from revoked consent."""
import time

import httpx
import pytest

from app.sources.base import SourceError
from app.sources.drive import DriveAdapter


@pytest.mark.parametrize('failure', ['network', 429, 500, 502, 503, 504])
def test_transient_refresh_failure_is_retryable_without_file_request(failure):
    credentials = {'access_token': 'old-synthetic', 'refresh_token': 'private-synthetic', 'expires_at': 0}
    original = credentials.copy()
    requests, persisted = [], []

    def respond(request):
        requests.append(request)
        assert request.url.path == '/token'
        if failure == 'network':
            raise httpx.ConnectError('synthetic outage', request=request)
        return httpx.Response(failure, json={'error': 'temporarily_unavailable'})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        adapter = DriveAdapter(credentials, persisted.append, client)
        with pytest.raises(SourceError) as caught:
            adapter.get_file('synthetic-folder')
    assert caught.value.retryable is True
    assert caught.value.code in {'drive_network', 'drive_unavailable'}
    assert len(requests) == 1
    assert credentials == original and persisted == []
    assert 'private-synthetic' not in str(caught.value)


@pytest.mark.parametrize('status,error', [(400, 'invalid_grant'), (401, 'invalid_client')])
def test_revoked_or_invalid_refresh_requires_reconnection(status, error):
    credentials = {'access_token': 'old-synthetic', 'refresh_token': 'private-synthetic', 'expires_at': 0}
    original = credentials.copy()
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, json={'error': error}))) as client:
        with pytest.raises(SourceError) as caught:
            DriveAdapter(credentials, client=client).get_file('synthetic-folder')
    assert caught.value.code == 'drive_reconnect'
    assert caught.value.retryable is False
    assert credentials == original


@pytest.mark.parametrize('body', [[], {}, {'access_token': ''}, {'access_token': 'new-synthetic', 'expires_in': 'invalid'}, {'access_token': 'new-synthetic', 'expires_in': 0}])
def test_malformed_refresh_never_replaces_stored_credentials(body):
    credentials = {'access_token': 'old-synthetic', 'refresh_token': 'private-synthetic', 'expires_at': 0}
    original = credentials.copy()
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as client:
        with pytest.raises(SourceError) as caught:
            DriveAdapter(credentials, client=client).get_file('synthetic-folder')
    assert caught.value.code == 'drive_unavailable'
    assert caught.value.retryable is True
    assert credentials == original


def test_successful_refresh_persists_once_and_reads_with_new_access_token():
    credentials = {'access_token': 'old-synthetic', 'refresh_token': 'private-synthetic', 'expires_at': 0}
    persisted, paths = [], []

    def respond(request):
        paths.append(request.url.path)
        if request.url.path == '/token':
            return httpx.Response(200, json={'access_token': 'new-synthetic', 'expires_in': 3600, 'token_type': 'Bearer'})
        assert request.headers['Authorization'] == 'Bearer new-synthetic'
        return httpx.Response(200, json={'id': 'synthetic-folder'})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        adapter = DriveAdapter(credentials, lambda value: persisted.append(value.copy()), client)
        assert adapter.get_file('synthetic-folder')['id'] == 'synthetic-folder'
        assert adapter.get_file('synthetic-folder')['id'] == 'synthetic-folder'
    assert paths == ['/token', '/drive/v3/files/synthetic-folder', '/drive/v3/files/synthetic-folder']
    assert len(persisted) == 1
    assert credentials['refresh_token'] == 'private-synthetic'
    assert credentials['expires_at'] > time.time() + 3500

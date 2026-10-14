"""Local connected startup reports configuration names, never secret values."""
from cryptography.fernet import Fernet

from app.settings import settings
from app.local_connected_check import issues, main


def test_missing_local_setup_fails_with_safe_guidance(monkeypatch, capsys):
    monkeypatch.setattr(settings, 'app_mode', 'live')
    for field in ['oidc_issuer','oidc_client_id','oidc_client_secret','api_key','model',
                  'drive_client_id','drive_client_secret','credentials_key','drive_redirect_uri']:
        monkeypatch.setattr(settings, field, None)
    assert main() == 1
    output = capsys.readouterr().out
    assert 'OIDC_CLIENT_ID is missing' in output
    assert 'DRIVE_CLIENT_ID is missing' in output
    assert 'localhost.env' in output


def test_configured_local_setup_is_presence_only(monkeypatch, capsys):
    values = {
        'app_mode':'live', 'oidc_issuer':'https://accounts.google.com',
        'oidc_client_id':'synthetic-client', 'oidc_client_secret':'synthetic-private-client',
        'api_key':'synthetic-private-api', 'model':'synthetic-model',
        'drive_client_id':'synthetic-client', 'drive_client_secret':'synthetic-private-client',
        'credentials_key':Fernet.generate_key().decode(), 'session_secret':'synthetic-private-session-' * 3,
        'drive_redirect_uri':'http://127.0.0.1:3000/api/v1/connections/drive/callback',
        'public_url':'http://127.0.0.1:3000', 'frontend_url':'http://127.0.0.1:3000',
    }
    for name,value in values.items():
        monkeypatch.setattr(settings, name, value)
    assert issues() == [] and main() == 0
    output = capsys.readouterr().out
    for name in ['oidc_client_secret','api_key','credentials_key','session_secret']:
        assert values[name] not in output
    assert 'remain to be verified' in output

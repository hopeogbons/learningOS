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


def test_raw_quoted_key_is_actionable_without_exposing_it(monkeypatch, capsys):
    secret=Fernet.generate_key().decode()
    monkeypatch.setattr(settings,'credentials_key','"'+secret+'"')
    assert main(json_output=True)==1
    output=capsys.readouterr().out
    assert 'TOKEN_ENCRYPTION_KEY has surrounding quotes' in output
    assert secret not in output


def test_localhost_registration_is_supported_and_report_is_safe(monkeypatch, capsys):
    import json
    monkeypatch.setattr(settings,'public_url','http://localhost:3000')
    monkeypatch.setattr(settings,'frontend_url','http://localhost:3000')
    monkeypatch.setattr(settings,'drive_redirect_uri','http://localhost:3000/api/v1/connections/drive/callback')
    main(json_output=True)
    data=json.loads(capsys.readouterr().out)
    assert data['expected_callbacks']['drive']=='http://localhost:3000/api/v1/connections/drive/callback'
    assert data['database_seed_required'] is False
    assert not any('PUBLIC_URL and FRONTEND_URL' in x for x in data['issues'])
    monkeypatch.setattr(settings,'public_url','http://private-secret@localhost:3000/?key=private-secret')
    main(json_output=True)
    output=capsys.readouterr().out
    assert 'private-secret' not in output
    assert 'PUBLIC_URL and FRONTEND_URL' in output


def test_unmapped_ports_and_ipv6_cannot_pass_docker_preflight(monkeypatch):
    for origin in ('http://localhost:8000','http://localhost:3030','http://[::1]:3000'):
        monkeypatch.setattr(settings,'public_url',origin)
        monkeypatch.setattr(settings,'frontend_url',origin)
        monkeypatch.setattr(settings,'drive_redirect_uri',origin+'/api/v1/connections/drive/callback')
        assert any('mapped frontend port 3000' in issue for issue in issues())
    monkeypatch.setattr(settings,'public_url','http://localhost:13320')
    monkeypatch.setattr(settings,'frontend_url','http://localhost:13320')
    monkeypatch.setattr(settings,'drive_redirect_uri','http://localhost:13320/api/v1/connections/drive/callback')
    assert not any('mapped frontend port' in issue for issue in issues(expected_web_port=13320))

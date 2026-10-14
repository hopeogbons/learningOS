"""Fail fast for the explicit connected-local Docker profile; never print secrets."""
import argparse
import json
from urllib.parse import urlsplit
from cryptography.fernet import Fernet

from .settings import settings
from .sources.drive import connection_setup_state


def issues(expected_web_port=3000):
    result = []
    if settings.app_mode not in {'live', 'connected'}:
        result.append('APP_MODE must be live or connected')
    for name, value in (
        ('OIDC_ISSUER', settings.oidc_issuer),
        ('OIDC_CLIENT_ID', settings.oidc_client_id),
        ('OIDC_CLIENT_SECRET', settings.oidc_client_secret),
        ('OPENROUTER_API_KEY' if settings.llm_provider == 'openrouter' else 'LEARNING_OS_API_KEY', settings.api_key),
        ('OPENROUTER_MODEL' if settings.llm_provider == 'openrouter' else 'LLM_MODEL', settings.model),
        ('DRIVE_CLIENT_ID', settings.drive_client_id),
        ('DRIVE_CLIENT_SECRET', settings.drive_client_secret),
        ('TOKEN_ENCRYPTION_KEY', settings.credentials_key),
        ('DRIVE_REDIRECT_URI', settings.drive_redirect_uri),
    ):
        if not value:
            result.append(name + ' is missing')
    if not settings.oidc_issuer or not settings.oidc_issuer.startswith('https://'):
        result.append('OIDC_ISSUER requires HTTPS')
    if len(settings.session_secret) < 32 or settings.session_secret.startswith('local-demo'):
        result.append('SESSION_SIGNING_KEY requires a generated private value')
    for name,value in (('OIDC_CLIENT_ID',settings.oidc_client_id),('OIDC_CLIENT_SECRET',settings.oidc_client_secret),
                       ('DRIVE_CLIENT_ID',settings.drive_client_id),('DRIVE_CLIENT_SECRET',settings.drive_client_secret),
                       ('TOKEN_ENCRYPTION_KEY',settings.credentials_key),('SESSION_SIGNING_KEY',settings.session_secret),
                       ('OPENROUTER_API_KEY' if settings.llm_provider == 'openrouter' else 'LEARNING_OS_API_KEY',settings.api_key),('OPENROUTER_MODEL' if settings.llm_provider == 'openrouter' else 'LLM_MODEL',settings.model)):
        if value and value[:1] in {'"', "'"} and value[-1:] == value[:1]:
            result.append(name + ' has surrounding quotes; Docker raw values must be unquoted')
    try:
        Fernet((settings.credentials_key or '').encode())
    except (ValueError,TypeError):
        result.append('TOKEN_ENCRYPTION_KEY must be a valid private Fernet key')
    try:
        origin = urlsplit(settings.public_url)
        valid_origin = (origin.scheme == 'http' and origin.hostname in {'localhost', '127.0.0.1'}
                        and origin.port == expected_web_port and not origin.username and not origin.password
                        and origin.path in {'','/'} and not origin.query and not origin.fragment)
    except ValueError:
        valid_origin = False
    if not valid_origin or settings.frontend_url.rstrip('/') != settings.public_url.rstrip('/'):
        result.append('PUBLIC_URL and FRONTEND_URL must use the same localhost HTTP origin on the mapped frontend port '+str(expected_web_port))
    if settings.drive_redirect_uri != settings.public_url.rstrip('/') + '/api/v1/connections/drive/callback':
        result.append('DRIVE_REDIRECT_URI must match PUBLIC_URL and /api/v1/connections/drive/callback exactly')
    if connection_setup_state() != 'ready':
        result.append('Drive setup requires usable token encryption and an exact callback matching PUBLIC_URL')
    return result


def report(expected_web_port=3000):
    callbacks={}
    try:
        origin=urlsplit(settings.public_url)
        if origin.scheme=='http' and origin.hostname in {'localhost','127.0.0.1'} and origin.port==expected_web_port:
            hostname='['+origin.hostname+']' if ':' in origin.hostname else origin.hostname
            safe_origin='http://'+hostname+':'+str(origin.port)
            callbacks={'sign_in':safe_origin+'/api/v1/auth/callback',
                       'drive':safe_origin+'/api/v1/connections/drive/callback'}
    except ValueError:
        pass
    failures=issues(expected_web_port)
    return {'mode':settings.app_mode,'configuration':'incomplete' if failures else 'present-unverified',
            'issues':failures, 'expected_callbacks':callbacks,
            'database_seed_required':False,
            'external_verification':'Google registration, sign-in, consent, and provider access remain to be verified'}


def main(json_output=False,expected_web_port=3000):
    if json_output:
        data=report(expected_web_port)
        print(json.dumps(data,indent=2))
        return 1 if data['issues'] else 0
    failures = issues(expected_web_port)
    if failures:
        print('Connected localhost setup is incomplete:')
        for failure in failures:
            print('- ' + failure)
        print('Initialize or complete the private settings with: docker compose --profile init run --build --rm --no-deps init')
        print('Edit the private localhost.env file using docs/LOCALHOST_STAGING.md; do not paste secret values into chat.')
        return 1
    print('Local configuration is present; Google registration, sign-in, consent, and provider access remain to be verified.')
    return 0


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true')
    parser.add_argument('--expected-web-port',type=int,default=3000,help='Must match an explicit frontend Docker port mapping; default 3000.')
    args=parser.parse_args()
    if not 1<=args.expected_web_port<=65535:
        parser.error('Expected frontend port must be between 1 and 65535.')
    raise SystemExit(main(args.json,args.expected_web_port))

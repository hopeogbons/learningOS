"""Fail fast for the explicit connected-local Docker profile; never print secrets."""
from urllib.parse import urlsplit

from .settings import settings
from .sources.drive import connection_setup_state


def issues():
    result = []
    if settings.app_mode not in {'live', 'connected'}:
        result.append('APP_MODE must be live or connected')
    for name, value in (
        ('OIDC_ISSUER', settings.oidc_issuer),
        ('OIDC_CLIENT_ID', settings.oidc_client_id),
        ('OIDC_CLIENT_SECRET', settings.oidc_client_secret),
        ('LEARNING_OS_API_KEY', settings.api_key),
        ('LLM_MODEL', settings.model),
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
    origin = urlsplit(settings.public_url)
    if (origin.scheme != 'http' or origin.hostname not in {'localhost', '127.0.0.1', '::1'}
            or settings.frontend_url != settings.public_url):
        result.append('PUBLIC_URL and FRONTEND_URL must use the same localhost HTTP origin')
    if connection_setup_state() != 'ready':
        result.append('Drive setup requires usable token encryption and an exact callback matching PUBLIC_URL')
    return result


def main():
    failures = issues()
    if failures:
        print('Connected localhost setup is incomplete:')
        for failure in failures:
            print('- ' + failure)
        print('Edit the private localhost.env file using docs/LOCALHOST_STAGING.md; do not paste secret values into chat.')
        return 1
    print('Local configuration is present; Google registration, sign-in, consent, and provider access remain to be verified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

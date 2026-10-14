#!/usr/bin/env python3
"""Check required production configuration names without printing their values."""
from pathlib import Path
import base64
import os
import re
import sys
from urllib.parse import urlparse

path = Path(sys.argv[1]).resolve()
if path.stat().st_mode & 0o077:
    sys.exit('Production environment file must be private (chmod 600).')
values = dict(os.environ)
for line in path.read_text().splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        continue
    if not re.match(r'^[A-Z][A-Z0-9_]*=', stripped):
        sys.exit('Use literal NAME=value lines, without export statements or shell execution.')
    key, value = stripped.split('=', 1)
    if value[:1] in {'"', "'"}:
        if not value.endswith(value[0]):
            sys.exit('Unbalanced quotes in environment file.')
        value = value[1:-1]
    if '$' in value or '\n' in value:
        sys.exit('Environment review requires literal values; resolve interpolation securely first.')
    values[key] = value
required = ['PUBLIC_DOMAIN', 'BACKEND_IMAGE', 'FRONTEND_IMAGE', 'DATABASE_URL', 'OIDC_ISSUER', 'OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET', 'SESSION_SIGNING_KEY', 'TOKEN_ENCRYPTION_KEY', 'STORAGE_ENDPOINT', 'STORAGE_REGION', 'STORAGE_BUCKET', 'STORAGE_ACCESS_KEY', 'STORAGE_SECRET_KEY', 'DRIVE_CLIENT_ID', 'DRIVE_CLIENT_SECRET', 'DRIVE_REDIRECT_URI']
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.llm_config import llm_configuration
provider, provider_key, provider_model = llm_configuration(values)
required += ['OPENROUTER_API_KEY'] if provider == 'openrouter' else ['LEARNING_OS_API_KEY']
missing = [key for key in required if not values.get(key)]
if not provider_model:
    missing.append('OPENROUTER_MODEL' if provider == 'openrouter' else 'LLM_MODEL')
if missing:
    sys.exit('Missing production settings: ' + ', '.join(missing))
if values.get('APP_MODE') != 'production':
    sys.exit('APP_MODE must be production.')
if not values['DATABASE_URL'].startswith('postgresql'):
    sys.exit('Production DATABASE_URL must use PostgreSQL.')
if len(values['SESSION_SIGNING_KEY']) < 32 or len(values['TOKEN_ENCRYPTION_KEY']) < 32:
    sys.exit('Session and token-protection keys need strong securely generated values.')
try:
    if len(base64.urlsafe_b64decode(values['TOKEN_ENCRYPTION_KEY'])) != 32:
        raise ValueError
except (ValueError, TypeError):
    sys.exit('TOKEN_ENCRYPTION_KEY must be a valid securely generated Fernet key.')
for key in ('BACKEND_IMAGE', 'FRONTEND_IMAGE'):
    if not re.search(r'@sha256:[0-9a-f]{64}$', values[key]):
        sys.exit('Production images must use reviewed immutable @sha256 digests.')
for key in ('OIDC_ISSUER', 'DRIVE_REDIRECT_URI', 'STORAGE_ENDPOINT'):
    parsed = urlparse(values[key])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        sys.exit(f'{key} requires a verified HTTPS endpoint without URL credentials.')
if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', values['PUBLIC_DOMAIN']) or '.' not in values['PUBLIC_DOMAIN']:
    sys.exit('PUBLIC_DOMAIN must be a DNS hostname, without scheme or port.')
origin = 'https://' + values['PUBLIC_DOMAIN']
for key in ('APP_ORIGIN', 'PUBLIC_URL', 'FRONTEND_URL'):
    if values.get(key) and values[key].rstrip('/') != origin:
        sys.exit(f'{key} must match the HTTPS origin derived from PUBLIC_DOMAIN.')
if values['DRIVE_REDIRECT_URI'] != origin + '/api/v1/connections/drive/callback':
    sys.exit('DRIVE_REDIRECT_URI must match PUBLIC_DOMAIN and /api/v1/connections/drive/callback exactly.')
print('Required production names, private file permissions, HTTPS URLs, mode and immutable image syntax passed. No external connection was made.')

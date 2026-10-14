#!/usr/bin/env python3
"""Create a private localhost template; never overwrite settings or copy secrets."""
import base64
import json
import os
from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parents[1]


def prepare(root=ROOT):
    runtime = root / '.runtime' / 'localhost'
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = runtime / 'localhost.env'
    values = {
        'LEARNING_OS_RUNTIME_DIR': str(runtime),
        'DATABASE_URL': 'sqlite:///' + str(runtime / 'learningos.db'),
        'PRIVATE_STORAGE_DIR': str(runtime / 'private'),
        'SESSION_SIGNING_KEY': secrets.token_urlsafe(48),
        'TOKEN_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
    }
    lines = []
    for line in (root / 'deploy' / 'localhost.env.example').read_text().splitlines():
        name = line.partition('=')[0]
        if name in values:
            line = name + '=' + json.dumps(values[name])
        lines.append(line)
    # O_EXCL refuses an existing file or symlink; do not replace encryption keys.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('\n'.join(lines) + '\n')
    return target


if __name__ == '__main__':
    try:
        result = prepare()
    except FileExistsError:
        raise SystemExit('Localhost settings already exist; retain and edit the existing private file.')
    print('Created private localhost settings at ' + str(result))
    print('Fill provider and Google client settings privately. Keys and data remain outside Git.')

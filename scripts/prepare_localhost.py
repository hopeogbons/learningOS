#!/usr/bin/env python3
"""Create or complete private localhost settings; preserve existing values and keys."""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def prepare(root=ROOT, docker=False):
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
    if docker:
        values.update({
            'LEARNING_OS_RUNTIME_DIR': '/data',
            'DATABASE_URL': 'sqlite:////data/learningos.db',
            'PRIVATE_STORAGE_DIR': '/data/private',
        })
    lines = []
    for line in (root / 'deploy' / 'localhost.env.example').read_text().splitlines():
        name = line.partition('=')[0]
        if name in values:
            # Compose's raw env_file treats quotes literally. Native uv accepts
            # JSON-quoted paths, including a checkout path containing spaces.
            line = name + '=' + (values[name] if docker else json.dumps(values[name]))
        lines.append(line)
    # O_EXCL refuses an existing file or symlink; never replace existing keys.
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if target.is_symlink():
            raise RuntimeError('Private localhost settings must be a regular file, not a symlink.')
        original=target.read_text()
        existing=original.splitlines()
        positions={line.partition('=')[0]:index for index,line in enumerate(existing)
                   if '=' in line and not line.lstrip().startswith('#')}
        # Preserve legacy aliases as well; generating a different token key
        # would prevent decrypting existing connections.
        aliases={'SESSION_SIGNING_KEY':'SESSION_SECRET','TOKEN_ENCRYPTION_KEY':'CREDENTIALS_KEY'}
        for line in lines:
            name,_,value=line.partition('=')
            if not name or name.startswith('#') or '=' not in line:
                continue
            alias=aliases.get(name)
            if alias in positions:
                alias_value=existing[positions[alias]].partition('=')[2]
                if alias_value.strip():value=alias_value
            if name not in positions:
                positions[name]=len(existing);existing.append(name+'='+value)
            elif not existing[positions[name]].partition('=')[2].strip() and value:
                existing[positions[name]]=name+'='+value
        updated='\n'.join(existing)+'\n'
        if updated != original:
            # A private atomic replacement preserves values and protects against
            # losing edits made while the initializer was preparing defaults.
            fd,temp_path=tempfile.mkstemp(prefix='.localhost-',dir=runtime)
            try:
                with os.fdopen(fd,'w') as stream:stream.write(updated)
                if target.is_symlink() or target.read_text()!=original:
                    raise RuntimeError('Localhost settings changed during initialization; retained, please retry.')
                os.replace(temp_path,target)
            finally:
                if os.path.exists(temp_path):os.unlink(temp_path)
        return target
    with os.fdopen(fd, 'w') as stream:
        stream.write('\n'.join(lines) + '\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker', action='store_true', help='Use /data paths and literal values for Docker Compose raw env_file.')
    args = parser.parse_args()
    try:
        result = prepare(docker=args.docker)
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(1)
    print('Private localhost settings prepared at ' + str(result))
    print('Missing defaults and local keys were initialized; existing values and keys were retained.')
    if args.docker:
        print('Docker raw values must be unquoted. Preserve existing key contents when removing native-generated surrounding quotes.')
    print('Fill provider and Google client settings privately. Keys and data remain outside Git.')

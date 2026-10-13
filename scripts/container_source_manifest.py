#!/usr/bin/env python3
"""Fingerprint Docker source inputs, excluding private and generated files.

Use --sanitize-existing to remove ignored records from an earlier build snapshot
without replacing its captured hashes with post-build development files.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.runtime', 'node_modules', '.venv', '__pycache__', '.pytest_cache', '.ruff_cache', '.git', 'test-results', 'playwright-report'}


def allowed(name):
    path = Path(name)
    return not any(part in IGNORED or part.startswith('.next') or part.endswith('.tsbuildinfo') or (part.startswith('.env') and not part.endswith('.example')) for part in path.parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/evidence/container-source-manifest.json')
    parser.add_argument('--sanitize-existing', type=Path)
    args = parser.parse_args()
    path = args.sanitize_existing or args.output
    if args.sanitize_existing:
        manifest = json.loads(path.read_text())
        files = {name: digest for name, digest in manifest['files'].items() if allowed(name)}
        manifest['snapshot_note'] = 'Preserves hashes captured for this image build; sanitization removed ignored private/generated records and did not fingerprint later development changes.'
    else:
        files = {}
        for directory in ('backend', 'frontend', 'fixtures', 'contracts', 'deploy'):
            for source in sorted((ROOT / directory).rglob('*')):
                name = source.relative_to(ROOT).as_posix()
                if source.is_file() and not source.is_symlink() and allowed(name):
                    files[name] = hashlib.sha256(source.read_bytes()).hexdigest()
        manifest = {'schema_version': 1, 'snapshot_note': 'Hashes captured when this manifest was generated; preserve this snapshot with its corresponding image build.'}
    manifest.update(files=files, file_count=len(files), aggregate_sha256=hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), scope='backend/frontend/fixtures/contracts/deploy source inputs; excludes private runtime, dependencies, build/type caches, Git and non-example environment files')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest': path.name, 'file_count': manifest['file_count'], 'aggregate_sha256': manifest['aggregate_sha256']}))


if __name__ == '__main__':
    main()

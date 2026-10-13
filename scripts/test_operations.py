#!/usr/bin/env python3
"""Synthetic safety regression checks for private backup/restore operations."""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import backup as operations

class BackupSafety(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='learningos-operations-test-')
        self.root = Path(self.directory.name)
        self.database = self.root / 'source.sqlite3'
        with sqlite3.connect(self.database) as db:
            db.executescript('''CREATE TABLE sources(id INTEGER PRIMARY KEY, hash TEXT NOT NULL);
                CREATE TABLE history(id INTEGER PRIMARY KEY, source_id INTEGER REFERENCES sources(id), next_review TEXT);
                INSERT INTO sources VALUES(1,'synthetic-source-sha');
                INSERT INTO history VALUES(1,1,'2026-10-20T12:00:00Z');''')
            db.execute('PRAGMA journal_mode=WAL')
        self.objects = self.root / 'private'
        self.objects.mkdir()
        (self.objects / 'synthetic-original').write_bytes(b'Synthetic backup-only source')
        self.output = self.root / 'backup'
        self.env = patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///' + str(self.database), 'PRIVATE_STORAGE_DIR': str(self.objects), 'STORAGE_BUCKET': '', 'S3_BUCKET': ''})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def make_backup(self):
        with redirect_stdout(io.StringIO()):
            operations.backup(argparse.Namespace(output=self.output, quiesced=True))

    def test_requires_explicit_quiescence(self):
        with self.assertRaisesRegex(ValueError, 'Stop API/worker'):
            operations.backup(argparse.Namespace(output=self.output, quiesced=False))
        self.assertFalse(self.output.exists())

    def test_never_overwrites_existing_backup(self):
        self.output.mkdir()
        sentinel = self.output / 'sentinel'
        sentinel.write_bytes(b'Existing private backup')
        with self.assertRaisesRegex(ValueError, 'never overwritten'):
            self.make_backup()
        self.assertEqual(sentinel.read_bytes(), b'Existing private backup')

    def test_isolated_restore_preserves_rows_and_objects_without_source_mutation(self):
        self.make_backup()
        source_signature = operations.sha(self.database)
        with redirect_stdout(io.StringIO()):
            operations.restore_check(argparse.Namespace(backup=self.output))
        self.assertEqual(operations.sha(self.database), source_signature)
        manifest = json.loads((self.output / 'manifest.json').read_text())
        self.assertEqual(manifest['tables']['history']['count'], 1)
        self.assertNotIn('database.sqlite3-wal', manifest['files'])
        self.assertNotIn('database.sqlite3-shm', manifest['files'])

    def test_detects_private_object_tampering(self):
        self.make_backup()
        (self.output / 'objects/synthetic-original').write_bytes(b'Altered bytes')
        with self.assertRaisesRegex(ValueError, 'integrity verification failed'):
            operations.restore_check(argparse.Namespace(backup=self.output))

    def test_manifest_cannot_escape_backup_root(self):
        self.make_backup()
        manifest = json.loads((self.output / 'manifest.json').read_text())
        manifest['files']['../source.sqlite3'] = operations.sha(self.database)
        (self.output / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'integrity verification failed'):
            operations.restore_check(argparse.Namespace(backup=self.output))

    def test_does_not_follow_private_object_symlinks(self):
        (self.objects / 'linked-source').symlink_to(self.database)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            self.make_backup()

if __name__ == '__main__':
    unittest.main(verbosity=2)

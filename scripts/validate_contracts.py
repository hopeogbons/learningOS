#!/usr/bin/env python3
"""Check versioned JSON schemas and the actual resumable orchestration state."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator

root = Path(__file__).resolve().parents[1]
files = sorted((root / 'contracts').glob('*.schema.json'))
if not files:
    raise SystemExit('No contract schemas found')
for path in files:
    Draft202012Validator.check_schema(json.loads(path.read_text()))
state_schema = json.loads((root / 'contracts/build-state.schema.json').read_text())
state_errors = sorted(
    Draft202012Validator(state_schema).iter_errors(json.loads((root / 'docs/build-state.json').read_text())),
    key=lambda error: str(list(error.absolute_path)),
)
if state_errors:
    for error in state_errors:
        location = '.'.join(map(str, error.absolute_path)) or '<root>'
        print(f'build-state.json {location}: {error.message}')
    raise SystemExit(1)
registry = json.loads((root / 'contracts/language-registry.json').read_text())['languages']
assert len(registry) == 10 and len({item['ui_locale'] for item in registry}) == 10
print(f'{len(files)} JSON schemas, current build state and ten-language registry passed.')

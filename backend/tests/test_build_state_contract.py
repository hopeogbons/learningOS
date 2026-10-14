"""Keep published orchestration state compatible with its strict CI contract."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]


def documents():
    schema = json.loads((ROOT / 'contracts/build-state.schema.json').read_text())
    state = json.loads((ROOT / 'docs/build-state.json').read_text())
    return Draft202012Validator(schema), state


def test_current_published_state_satisfies_contract():
    validator, state = documents()
    validator.validate(state)


def test_legacy_state_without_maintenance_history_remains_valid():
    validator, state = documents()
    state.pop('maintenance_updates', None)
    validator.validate(state)


@pytest.mark.parametrize('mutation', ['unknown_field', 'invalid_test_count', 'invalid_commit'])
def test_maintenance_contract_rejects_invalid_evidence(mutation):
    validator, state = documents()
    state = copy.deepcopy(state)
    update = state['maintenance_updates'][0]
    if mutation == 'unknown_field':
        update['invented_status'] = 'passed'
    elif mutation == 'invalid_test_count':
        update['backend']['passed'] = '178'
    else:
        update['deployment']['source_commit'] = 'not-a-commit'
    assert list(validator.iter_errors(state))

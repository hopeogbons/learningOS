"""Regressions from a real provider's citation-free teaching response."""
import json

import jsonschema
import pytest

from app.llm import InvalidModelOutput, OpenAIProvider


@pytest.mark.parametrize("quote_present", [True, False])
def test_outbound_turn_contract_requires_original_quote(monkeypatch, quote_present):
    monkeypatch.setenv("LEARNING_OS_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("LLM_MODEL", "synthetic-test-model")
    context = {
        "study_locale": "fr",
        "concepts": [{"id": "concept-protons", "text": "Atomic number equals proton count."}],
        "citations": [{"id": "original-line", "excerpt": "Atomic number equals proton count."}],
    }
    turn = {
        "teaching": "Le numéro atomique correspond au nombre de protons.",
        "question": "Que représente le numéro atomique ?",
        "expected_answer": "Le nombre de protons.",
        "concept_ids": ["concept-protons"],
        "citation_ids": ["original-line"],
        "source_quotes": [{"citation_id": "original-line", "quote": "Atomic number equals proton count."}] if quote_present else [],
    }
    provider = OpenAIProvider()

    def request(path, **kwargs):
        assert path == "chat/completions"
        schema = kwargs["json"]["response_format"]["json_schema"]["schema"]
        if quote_present:
            jsonschema.validate(turn, schema)
        else:
            # The actual outgoing constrained-generation contract must forbid
            # the response observed in the live smoke, before local validation.
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(turn, schema)
        return {"choices": [{"message": {"content": json.dumps(turn)}}]}

    monkeypatch.setattr(provider, "_request", request)
    if quote_present:
        output = provider.generate("turn", context)
        assert output["source_quotes"][0]["quote"] == context["citations"][0]["excerpt"]
        assert output["teaching"] == turn["teaching"]
    else:
        with pytest.raises(InvalidModelOutput):
            provider.generate("turn", context)


@pytest.mark.parametrize("duplicate", [None, "evidence_event_ids", "citation_ids"])
def test_reviewer_provider_subset_retains_local_duplicate_guard(monkeypatch, duplicate):
    monkeypatch.setenv("LEARNING_OS_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("LLM_MODEL", "synthetic-test-model")
    context = {
        "item_id": "attempt", "confidence": 5,
        "concepts": [{"id": "concept", "text": "Proton count."}],
        "citations": [{"id": "source", "excerpt": "Proton count."}],
        "evidence_event_ids": ["event"],
    }
    verdict = {
        "item_id": "attempt", "confidence": 5, "correctness": "correct",
        "missing_parts": [], "guessing_signal": "unsupported",
        "feedback": "Correct.", "title_complete": True, "rationale": "Cited proton count.",
        "evidence_event_ids": ["event"], "citation_ids": ["source"],
    }
    if duplicate:
        verdict[duplicate] *= 2
    provider = OpenAIProvider()

    def request(path, **kwargs):
        schema = kwargs["json"]["response_format"]["json_schema"]["schema"]
        assert "uniqueItems" not in json.dumps(schema)
        jsonschema.validate(verdict, schema)
        return {"choices": [{"message": {"content": json.dumps(verdict)}}]}

    monkeypatch.setattr(provider, "_request", request)
    if duplicate:
        with pytest.raises(InvalidModelOutput):
            provider.generate("assessment", context)
    else:
        assert provider.generate("assessment", context)["evidence_event_ids"] == ["event"]

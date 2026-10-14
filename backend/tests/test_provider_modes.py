"""CI test mode is offline; missing live credentials must never cause fallback."""
import pytest

from app.llm import DemoProvider, ProviderUnavailable, get_provider
from app.settings import settings


@pytest.mark.parametrize("mode", ["demo", "test"])
def test_fixture_modes_run_without_keys_or_network(monkeypatch, mode):
    monkeypatch.setattr(settings, "app_mode", mode)
    monkeypatch.delenv("LEARNING_OS_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("An offline fixture tried to call the live provider")

    monkeypatch.setattr("app.llm.OpenAIProvider._request", forbidden)
    provider = get_provider()
    assert isinstance(provider, DemoProvider)
    context = {
        "study_locale": "en", "mode": "study",
        "concepts": [{"id": "protons", "text": "Atomic number is proton count."}],
        "citations": [{"id": "original", "excerpt": "Atomic number is proton count."}],
    }
    turn = provider.generate("turn", context)
    assert turn["citation_ids"] == ["original"]
    assert turn["source_quotes"] == [{"citation_id": "original", "quote": context["citations"][0]["excerpt"]}]
    with pytest.raises(ProviderUnavailable):
        provider.vision(b"synthetic-unreadable-image", "image/png")


@pytest.mark.parametrize("mode", ["live", "connected", "production"])
def test_missing_live_key_does_not_select_fixture(monkeypatch, mode):
    monkeypatch.setattr(settings, "app_mode", mode)
    monkeypatch.delenv("LEARNING_OS_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(ProviderUnavailable):
        get_provider()

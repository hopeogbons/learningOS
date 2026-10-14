"""One non-secret routing rule for runtime, readiness and deployment checks."""
import os


def llm_configuration(values=None):
    values = os.environ if values is None else values
    provider = values.get("LLM_PROVIDER", "auto").strip().lower() or "auto"
    if provider not in {"auto", "openai", "openrouter"}:
        raise RuntimeError("LLM_PROVIDER must be auto, openai or openrouter")
    if provider == "auto":
        provider = "openai" if values.get("LEARNING_OS_API_KEY") else "openrouter" if values.get("OPENROUTER_API_KEY") else "openai"
    if provider == "openrouter":
        return provider, values.get("OPENROUTER_API_KEY"), values.get("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    return provider, values.get("LEARNING_OS_API_KEY"), values.get("LLM_MODEL") or values.get("LEARNING_OS_MODEL", "")

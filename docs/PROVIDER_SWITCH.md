# Urgent demo provider switch

## Done when

Connected/live/production text teaching, assessment and document vision select OpenAI or OpenRouter from the same server configuration used by readiness and staging checks. Existing source/schema/ownership validation remains mandatory. Keys are separate and are never sent to the other provider. Demo/test modes remain deterministic. Only key routing/strict structured-output and speech-separation regressions are needed.

Set these unquoted lines in your private `.runtime/localhost/localhost.env` (never commit or paste keys):

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your-private-openrouter-key
OPENROUTER_MODEL=openai/gpt-4o-mini
```

Choose an OpenRouter model that supports strict JSON schema and images if OCR/vision is needed. The default OpenRouter model is `openai/gpt-4o-mini`. Requests enforce parameter-compatible provider routing and retain local output/source validation. OpenRouter API: https://openrouter.ai/api/v1/chat/completions; compatibility reference: https://github.com/OpenRouterTeam/typescript-sdk.

`LLM_PROVIDER=auto` (default) selects OpenAI while LEARNING_OS_API_KEY is nonempty, otherwise OpenRouter when OPENROUTER_API_KEY is set. Explicit `openrouter` overrides an existing OpenAI key; explicit `openai` switches back. There is no automatic mid-request retry to another company. Missing/invalid selected configuration fails clearly instead of silently using a different credential.

Keep LEARNING_OS_API_KEY, LLM_MODEL and speech settings for OpenAI live voice, STT and TTS. OpenRouter selection covers text/assessment/vision; it does not supply the implemented OpenAI Realtime service. Removing the OpenAI key disables server speech/live voice, while text remains available through OpenRouter. Browser speech may still be available.

After pulling this change, run `docker compose up -d --build backend worker` to install it and recreate services with the edited environment. Later key-only changes need `docker compose up -d --force-recreate backend worker`, not a rebuild. Existing learner data and Google settings remain intact. Production uses its reviewed private environment file.

A real OpenRouter call requires a usable separate key and permitted access to openrouter.ai. This managed cloud environment currently has neither configured OpenRouter credentials nor that destination grant; mocked routing checks cannot be claimed as live provider verification.

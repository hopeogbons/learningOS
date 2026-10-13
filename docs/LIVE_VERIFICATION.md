# Connected verification after secure configuration

The application is built for ten interface, study and speech languages. The offline suite verifies the contracts and UI; actual teaching, speech and Drive access remain required connected-release gates. The current results are in RELEASE_REPORT.md and language-support.json.

Use secure environment settings for LEARNING_OS_API_KEY and actual LLM_MODEL, STT_MODEL, TTS_MODEL and TTS_VOICE identifiers. The preflight checks names/presence and never prints the key. No model or voice identifier has been invented. Run from the repository:

```bash
backend/.venv/bin/python scripts/verify_live_learning.py --report .runtime/live-preflight.json
```

Without credentials this returns 2, makes zero provider calls, and records the missing names. Choose a new output path for every run; the verifier refuses to overwrite evidence. The frozen backend install supplies its dependencies.

Once the real provider is configured, the following explicit opt-in performs paid provider requests. It runs synthetic English-source teaching and correct/incorrect/low-confidence grading in all ten target languages, and clear/unreadable image probes through app/llm.py. The default preflight never makes these calls.

```bash
APP_MODE=live backend/.venv/bin/python scripts/verify_live_learning.py \
  --allow-provider-calls --sections text,vision \
  --private-review-dir .runtime/live-review/run-01 \
  --report .runtime/live-text-vision-01.json
```

Programmatic success establishes a bounded provider contract. Proficient speakers must review semantic accuracy, original citation fidelity and uncertainty handling before L03 is passed. Raw review outputs remain private under .runtime; do not attach real learner content to Git evidence.

For speech, prepare a private JSON manifest with consent `synthetic-or-explicitly-consented`. Its `languages` object maps each default speech tag from contracts/language-registry.json to exactly three records. Each record contains `audio` (path relative to the manifest), `mime`, `expected_transcript`, `expected_correctness` (correct/incorrect/partial/uncertain), and `confidence` (1–5). Use consented native-language recordings, at most 5 MiB and 60 seconds per turn. FFprobe is required for non-WAV duration validation. Example shape, with placeholders to replace:

```json
{
  "consent": "synthetic-or-explicitly-consented",
  "languages": {
    "en-GB": [
      {"audio": "turn-1.wav", "mime": "audio/wav", "expected_transcript": "Your reference transcript", "expected_correctness": "correct", "confidence": 5},
      {"audio": "turn-2.wav", "mime": "audio/wav", "expected_transcript": "Your reference transcript", "expected_correctness": "incorrect", "confidence": 4},
      {"audio": "turn-3.wav", "mime": "audio/wav", "expected_transcript": "Your reference transcript", "expected_correctness": "correct", "confidence": 2}
    ]
  }
}
```

Provide all ten tags for the all-ten gate. Then run `--allow-provider-calls --sections speech --speech-manifest /absolute/private/speech.json` with a fresh private review directory/report. A full text/vision/speech run can make up to 162 provider calls (40 text, 2 vision, 120 speech); review provider costs first. The probe temporarily enables only its supplied speech locales within its own process to test them; it does not certify or update the running application's VERIFIED_SPEECH_LOCALES. Native transcript review, listening to audio and an actual three-turn browser interaction remain required. Publish the verified allowlist only after that sign-off. Differing study/speech languages currently return an explicit unavailable state rather than mislabeling spoken output; same-language regional variants are supported targets.

For Drive, configure runtime DRIVE_CLIENT_ID, DRIVE_CLIENT_SECRET and DRIVE_REDIRECT_URI, actual OIDC sign-in, and a raw TOKEN_ENCRYPTION_KEY securely. A Codex personal connector is separate. Connect through the application's Connections page and grant the disclosed scopes. Run D01–D06 in DRIVE_INGESTION.md: automatic managed root/Collection folders; a UI original in its selected folder; an ordinary manually dropped file; an unchanged second sync producing no duplicate; changed revision; link descriptor; interruption/revocation; cross-user denial. Record only synthetic IDs, checks and hashes. Scope consent and Google testing/verification restrictions must be checked with actual accounts before availability to other clients is claimed.

Public links can be submitted while DNS is unavailable and stay visibly queued. Fetching still requires safe public DNS resolution, pinned addresses, revalidated redirects and verified TLS. This cloud's proxy-only egress has not proven that route. Test a permitted public page and captions source on the intended deployment network; never disable SSRF/TLS checks to make a test pass.

Production additionally needs real private S3 policy/object-access tests, actual OIDC issuer/client tests, domain/DNS/HTTPS, dependency/container scans and the scalability target. Follow DEPLOYMENT.md and the prepared private-environment Compose command. No public publication has been authorized or performed.

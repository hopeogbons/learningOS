# Connected staging on your own computer

The selected review target is localhost. A browser on your computer cannot reach the Codex cloud machine's loopback address. Download the current source package and run it on the same computer as your browser. This is a private connected review environment, not a public production deployment. The tested scripts require Linux Bash (or Windows WSL2), Git, Node.js 24, Python 3.12, uv, curl, and setsid.

## Install and prepare private settings

Unpack the source archive and enter its `learningOS` folder. Install the existing frozen locks, then create a separate connected-data directory and fresh local session/encryption keys:

```bash
bash scripts/setup.sh
python scripts/prepare_localhost.py
```

The first command prepares the labeled offline demo. The second creates `.runtime/localhost/localhost.env` with private permissions, local paths, and fresh generated keys. It refuses to overwrite an existing file. Do not regenerate the encryption key after connecting Drive; keep it with your private backups. No existing cloud secret is copied into the download or generated file.

Edit that private file locally. Fill `LEARNING_OS_API_KEY`, `LLM_MODEL`, `STT_MODEL`, `TTS_MODEL`, and `TTS_VOICE` with your actual provider settings. Fill the Google client names described below. Keep `APP_MODE=live`, both origins, and the callback URI exactly as supplied. The connected database is separate from the synthetic demo. Leave `VERIFIED_SPEECH_LOCALES` empty until native transcripts, audible output, and browser exchanges have been checked for those locales; the UI retains typing fallback meanwhile.

## Google sign-in and Drive consent

Use an actual Google **Web application** OAuth client. Its consent screen must allow your test account; enable Google Drive API in that project. Review the requested scopes: `openid profile` for sign-in and `drive.file` plus `drive.readonly` for app-managed uploads and manually dropped-file discovery. The read scope is broad at the provider level; the application restricts its reads to connected Collection folders.

Register both exact authorized redirect URIs:

```text
http://127.0.0.1:3000/api/v1/auth/callback
http://127.0.0.1:3000/api/v1/connections/drive/callback
```

`127.0.0.1` is the loopback address for this localhost workflow. Use it consistently; `localhost` is a different OAuth redirect hostname. Set `OIDC_ISSUER=https://accounts.google.com`. The same Web client can serve these two flows: put its client ID into both `OIDC_CLIENT_ID` and `DRIVE_CLIENT_ID`, and its secret into both corresponding secret fields. Registration and consent must be completed in your Google account; configured variables alone do not establish a valid client. Do not put passwords, refresh tokens, or secret values in chat.

## Start the connected review

uv loads the private environment file as data, without executing its contents as shell code:

```bash
export UV_CACHE_DIR="$PWD/.runtime/uv-cache"
APP_MODE=live uv run --frozen --project backend --env-file "$PWD/.runtime/localhost/localhost.env" bash scripts/setup.sh
APP_MODE=live uv run --frozen --project backend --env-file "$PWD/.runtime/localhost/localhost.env" bash scripts/dev.sh
```

Open `http://127.0.0.1:3000` **on that computer**. Sign in with the permitted test account, then open Connections and connect Drive through Google's consent flow. The connected setup applies migrations without inserting a demo identity. The dev command runs API, durable worker, and frontend on loopback; keep that terminal running. Do not use the production Compose target with these HTTP/SQLite settings.

## Required connected checks

Create a synthetic Collection and confirm one managed Drive root/Collection folder. Upload a small synthetic note in Add Material and confirm the original appears in that exact folder and its Outline. Drop a different note manually into the same Drive folder, wait for polling or use Sync, and confirm it appears once in the correct Collection. Sync again: neither source may duplicate. Submit a permitted public link and confirm its descriptor/snapshot and cited material; failed external fetches must remain queued or Attention. Run the full D01–D06 interruption, revocation, revision, and cross-user checks from DRIVE_INGESTION.md before claiming live intake complete.

Study an original source in the target languages and review meaning and unchanged citations with proficient speakers (L03). For voice, use consented native-language recordings and perform actual microphone/three-turn exchanges, transcript review, and audible-output review (L04). Synthetic TTS/STT round trips are preliminary endpoint checks. Localhost is normally a browser secure context for microphone use; actual permission and browser capability still need testing.

To exercise a locale during a supervised L04 browser test, temporarily enable only that locale in the startup process (for example, prefix the connected dev command with `VERIFIED_SPEECH_LOCALES=en-GB APP_MODE=live`). This is a test override, not certification. Keep the saved private-file allowlist empty until that locale's native transcript, audibility, and three-turn checks pass, then record its evidence and enable only approved tags. Restore the unverified/typing state after an unsuccessful test. Never enable all ten based only on the synthetic endpoint report.

Production gates remain separate: PostgreSQL/private storage/OIDC/HTTPS, performance, restore/rollback, immutable new images, and an explicitly reviewed host. The former container images and build archive predate the connected-verification fixes and must not be described as containing them.

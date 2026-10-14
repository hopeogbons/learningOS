# Connected staging on your own computer

The selected review target is localhost: the browser and Docker run on your own computer. The offline `compose.demo.yml` target cannot connect Drive; its Connect action must show unavailable. For real Google sign-in and Drive use the separate connected target below. It keeps connected user data in a different named volume from the synthetic demo.

## Diagnose the existing installation

The normal root `docker compose` command now uses connected mode, not the demo. Its project name and connected volume match the explicit connected target, so switching command style does not create another database. The older `deploy/compose.demo.yml` always forces demo mode and ignores Google credentials.

```text
docker compose --profile diagnose run --build --rm --no-deps diagnose
```

The report lists `mode`, missing/invalid configuration **names**, safe expected callbacks and `database_seed_required: false`. An incomplete report exits nonzero. It does not print keys, client secrets or tokens and does not establish that Google has accepted the credentials. Check `docker compose ps -a` for API/worker/frontend health. Health/readiness must show `live`, not `demo`.

Your actual private configuration is `.runtime/localhost/localhost.env`; a project-root `.env` is not the application's configuration file here. Setting endpoints in Google Console registers callbacks but does not populate this file. Rebuild/recreate after changing it. Do not seed or delete the connected database: the first successful Google sign-in creates your learner and you create your own Collections and content.

## Docker Desktop setup (Windows, macOS, or Linux)

Download the latest source from [GitHub](https://github.com/hopeogbons/learningOS) or update your existing checkout without discarding private settings. Open PowerShell or a terminal in the folder containing `README.md`. Install/start Docker Desktop (Linux containers on Windows), or Docker Engine with Compose on Linux. Docker provides Node and Python; host Node, Python, WSL terminal tools, and uv are not required for this path. Run `docker compose version`: version **2.30 or newer** is required because the private env file is read literally using `format: raw`.

Stop the offline demo to free ports 3000 and 8000. This retains its existing data:

```text
docker compose -f deploy/compose.demo.yml down
```

Create private connected settings using a one-shot container. In **Windows PowerShell or macOS Terminal**:

```text
docker compose -f deploy/compose.connected-local.yml --profile init run --build --rm --no-deps init
```

On **Linux**, run the helper as your host user so its private file is owned/editable by you:

```bash
docker compose -f deploy/compose.connected-local.yml --profile init run --build --rm --no-deps --user "$(id -u):$(id -g)" init
```

The helper creates `.runtime/localhost/localhost.env`, generates real random local session/encryption keys, and uses `/data` container paths. It creates the file with mode `0600` on Unix; Docker Desktop Windows file protection follows the host's ACLs, so keep the project in your private user directory. The init container has no network access after the image build. Running init again preserves existing nonblank values and keys, completes missing defaults, and generates only missing local keys. Empty/partial settings are repaired; provider credentials must still be entered privately. Do not regenerate the encryption key after connecting Drive; keep it with your private backups. No cloud secret is copied.

In Windows PowerShell open the file with:

```powershell
notepad .runtime\localhost\localhost.env
```

On macOS/Linux use your local text editor. Fill `LEARNING_OS_API_KEY` and `LLM_MODEL` with the actual provider key and a supported structured-output/vision model you have verified. Fill the Google client settings described below. Speech provider fields are needed when testing speech; leave `VERIFIED_SPEECH_LOCALES` empty until each language has native-transcript, audible-output, and browser evidence. Keep `APP_MODE=live` and the supplied origins/callback URI. Do not paste secrets into chat or Git.

The Docker env file is **literal data**, never shell code: write `NAME=value` with the actual value after `=`, without surrounding quotes or `export`, and never `source` it. Dollar signs and `#` inside values stay literal. If a previous native setup generated quoted key values, remove only the surrounding quotation marks from `SESSION_SIGNING_KEY` and `TOKEN_ENCRYPTION_KEY`, preserving the original key contents. Container data-path overrides are supplied by Compose; your prior native path defaults are not edited.

## Optional native setup

For Linux Bash/WSL2 with Git, Node.js 24, Python 3.12, uv, curl, and setsid already installed, the original frozen-lock path is still available:

```bash
bash scripts/setup.sh
python scripts/prepare_localhost.py
```

This creates native paths and does not replace an existing settings file. Choose one runtime at a time; native SQLite data and the connected Docker volume are distinct. Docker-generated `/data` values must be changed to actual private host paths before using that same file natively; retain the session/encryption keys.

## Google sign-in and Drive consent

Use an actual Google **Web application** OAuth client. Its consent screen must allow your test account; if the app is in Testing, add that Google account under its test users. Enable Google Drive API in that project. Review the requested scopes: `openid profile` for sign-in and `drive.file` plus `drive.readonly` for app-managed uploads and manually dropped-file discovery. The read scope is broad at the provider level; the application restricts its reads to connected Collection folders.

Register both exact authorized redirect URIs:

```text
http://127.0.0.1:3000/api/v1/auth/callback
http://127.0.0.1:3000/api/v1/connections/drive/callback
```

`127.0.0.1` is the template default. If your registered Google callbacks use `localhost`, retain that hostname instead: change `APP_ORIGIN`, `PUBLIC_URL`, `FRONTEND_URL` to `http://localhost:3000` and `DRIVE_REDIRECT_URI` to `http://localhost:3000/api/v1/connections/drive/callback`. Register both callbacks for that same origin and open it in the browser. Compose preserves the private-file origins. Do not mix the hostnames or point browser callbacks at backend port 8000. Set `OIDC_ISSUER=https://accounts.google.com`. The same Web client can serve these two flows: put its client ID into both `OIDC_CLIENT_ID` and `DRIVE_CLIENT_ID`, and its secret into both corresponding secret fields. Registration and consent must be completed in your Google account; configured variables alone do not establish a valid client. Do not put passwords, refresh tokens, or secret values in chat.

## Start the connected review

After saving the private settings and registering both callbacks, in **PowerShell or a terminal** run:

```text
docker compose -f deploy/compose.connected-local.yml up --build -d --wait
```

Open the browser origin you configured in `PUBLIC_URL` on that computer (the template defaults to **`http://127.0.0.1:3000`**). Sign in with your permitted Google test account, then open **Connections → Connect Drive** and grant the application's consent. Authentication uses Google OIDC; no demo identity is inserted. Missing/invalid local authentication or model configuration blocks startup/readiness rather than substituting demo success. Configuration presence is not proof Google/provider credentials work. The first frozen image build can take several minutes.

Both web/API ports bind only to `127.0.0.1`; connected state lives in the `learningos-connected-local_connected-data` volume. Stop with:

```text
docker compose -f deploy/compose.connected-local.yml down
```

Do not add `-v`: it deletes the connected database and private source files. Changes to the private env file require rerunning the `up` command to recreate affected containers. If startup fails, inspect service state and local logs:

```text
docker compose -f deploy/compose.connected-local.yml ps -a
docker compose -f deploy/compose.connected-local.yml logs --tail 80 migrate backend worker
```

Keep logs private and redact credential/account/source data before sharing errors. Do not run `docker compose config` with filled secrets and paste its output; that command may display them. An OAuth `redirect_uri_mismatch` requires the exact URI registrations above; an access-denied test account needs consent-screen/test-user or organization approval, rather than repeated Connect retries. A failure before Google's consent page is typically missing local configuration or use of the offline target.

For the optional **native** path only, uv reads the private file as data:

```bash
export UV_CACHE_DIR="$PWD/.runtime/uv-cache"
APP_MODE=live uv run --frozen --project backend --env-file "$PWD/.runtime/localhost/localhost.env" bash scripts/setup.sh
APP_MODE=live uv run --frozen --project backend --env-file "$PWD/.runtime/localhost/localhost.env" bash scripts/dev.sh
```

Keep that terminal running. Do not use production Compose with localhost HTTP/SQLite settings.

## Required connected checks

Create a synthetic Collection and confirm one managed Drive root/Collection folder. Upload a small synthetic note in Add Material and confirm the original appears in that exact folder and its Outline. Drop a different note manually into the same Drive folder, wait for polling or use Sync, and confirm it appears once in the correct Collection. Sync again: neither source may duplicate. Submit a permitted public link and confirm its descriptor/snapshot and cited material; failed external fetches must remain queued or Attention. Run the full D01–D06 interruption, revocation, revision, and cross-user checks from DRIVE_INGESTION.md before claiming live intake complete.

Study an original source in the target languages and review meaning and unchanged citations with proficient speakers (L03). For voice, use consented native-language recordings and perform actual microphone/three-turn exchanges, transcript review, and audible-output review (L04). Synthetic TTS/STT round trips are preliminary endpoint checks. Localhost is normally a browser secure context for microphone use; actual permission and browser capability still need testing.

To exercise a locale during a supervised L04 browser test, temporarily enable only that locale in the startup process (for example, prefix the connected dev command with `VERIFIED_SPEECH_LOCALES=en-GB APP_MODE=live`). This is a test override, not certification. Keep the saved private-file allowlist empty until that locale's native transcript, audibility, and three-turn checks pass, then record its evidence and enable only approved tags. Restore the unverified/typing state after an unsuccessful test. Never enable all ten based only on the synthetic endpoint report.

Production gates remain separate: PostgreSQL/private storage/OIDC/HTTPS, performance, restore/rollback, immutable new images, and an explicitly reviewed host. Rebuild the connected images from the updated checkout with `--build`; previously built demo images or downloaded archives may predate these fixes.

## Fast provider switch

Follow docs/PROVIDER_SWITCH.md to select OpenRouter with LLM_PROVIDER, OPENROUTER_API_KEY and OPENROUTER_MODEL in the same private localhost.env file. Text-provider readiness uses that selection. Keep the OpenAI key for the implemented speech/live voice services.

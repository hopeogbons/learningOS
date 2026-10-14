# Hosted connected beta

This is an optional future HTTPS deployment. The active delivery is the connected application on localhost; see LOCAL_HEALTH_REPORT.md. A hosted beta would let invited learners use real sign-in, AI, private uploads and Google Drive. No host is selected or accessible yet; this file is the launch handoff, not a deployed site. The user has requested deployment. Google/client account setup and hosting access remain external prerequisites.

## Supported deployment target

`deploy/compose.production.yml` runs Caddy, the supplied dashboard, FastAPI, a durable worker and a migration task on a Docker host. PostgreSQL and private S3 storage are external. Only HTTPS/HTTP edge ports are public. Existing production configuration checks reject missing credentials, mutable image references, conflicting origins and an incorrect Drive callback.

Use an existing account/server if available. A Render deployment needs a provider-specific service configuration and frontend proxy build target; the existing Compose file cannot be treated as a Render blueprint. Do not create paid resources until the host/account and spending authorization are established.

## Secure launch inputs

The operator supplies a hosting account/server, domain and DNS access, PostgreSQL connection and private S3 endpoint/bucket credentials. Populate the names in `deploy/.env.production.example` through the host's secret settings or a private environment file outside Git. AI keys that work through Codex's proxy are not assumed portable hosting credentials. Generate persistent session/encryption keys on the target; retain them across restarts.

Enable Google Drive API and configure a Google Web OAuth client and consent screen. Use the actual beta domain to register **both** HTTPS callbacks:

```text
https://<actual-domain>/api/v1/auth/callback
https://<actual-domain>/api/v1/connections/drive/callback
```

Set `OIDC_ISSUER=https://accounts.google.com`; the same Web client can supply the OIDC and Drive client settings. Set `DRIVE_REDIRECT_URI` to the second exact callback. Invite the beta cohort as Google test users when consent remains in testing. Consent scope behavior must be tested; testing credentials do not establish unrestricted public access. No secret values belong in chat or Git.

## Launch and verification

1. Freeze the reviewed Git commit; build the pinned Dockerfiles and push images to an authorized registry. Record the registry's actual immutable digests in `BACKEND_IMAGE` and `FRONTEND_IMAGE`.
2. Configure DNS and the private host settings. Run `scripts/release_check.sh --production /absolute/private/production.env`. A passing syntax check is not proof of external authentication/storage connectivity.
3. On the selected host, run the migration service once, then start the production Compose stack using that private environment file. Verify HTTPS and readiness before inviting learners.
4. With synthetic test accounts, verify Google sign-in, Drive consent, managed Collection folder creation, UI file/link intake into that folder, direct folder-drop ingestion, duplicate convergence, original citations, learning/review persistence and tenant isolation. Revoke/reconnect consent and verify failures remain explicit.
5. Verify a target-host backup/restore and worker restart. Record the accessible URL and the exact deployed commit/digests. If a gate fails, retain its evidence and use the reviewed rollback plan.

The 132-test PostgreSQL-backed offline suite, six desktop/mobile connection checks and frontend build passed for this source revision. Real AI text/vision probes passed previously. Actual Google consent/folder ingestion, target-host operation, native-language/voice approval and the failed latency target remain open in `RELEASE_REPORT.md`. An invited beta can collect feedback on these limits; it must not be described as a fully validated production release.

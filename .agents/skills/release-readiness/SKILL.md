---
name: release-readiness
description: Assess the Learning OS release candidate against live workflow, security, scalability and operations gates.
---

# Release Readiness


1. Read docs/DEPLOYMENT.md, ACCEPTANCE_TESTS.md, SECURITY_PRIVACY.md, SCALABILITY.md, capabilities.md and current state. Identify claimed release level and commit.
2. Run required frozen-install/build/backend/frontend/contract checks; verify executed counts and outcome. Test real authenticated user/source/session/review flows for the claimed mode, not fixture substitutes for live gates.
3. Audit tenant/auth/CSRF/private sources/idempotency/jobs/secret handling. Review original UI fidelity and voice fallback. Require PostgreSQL, measured load, independent code review and isolated backup/restore/rollback evidence for production.
4. Compare every Codex feature claim to native invocation artifact, client/version and runtime boundary. Configured-only/native-unverified stays labeled; application DB/scheduler/speech are not automatically native features.
5. Produce a release report with passed/failed/skipped/unrun/blocked, exact evidence and concrete external prerequisites. Prepare reviewable deployment config/command before publication approval. Never deploy or send messages solely because this skill was invoked.

Revision 2: read docs/INTERNATIONALIZATION.md and DRIVE_INGESTION.md. Verify localized output/RTL/source preservation and correct-folder UI/drop convergence when relevant; missing live proof stays blocked. All ten requested speech capabilities and actual scoped Drive writes need separate evidence.

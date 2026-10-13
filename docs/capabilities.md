# Capability ledger — initial observations, not release claims

Preparation date: 2026-10-13. CLI inspected: 0.159.2. Raw official repository config schema captured; developer-site access blocked by proxy. `validation/` records the preparation evidence. Fill separate development and runtime proof at each batch.

| Feature | Availability observed | Planned implementation | Verification now | Evidence needed |
|---|---|---|---|---|
| Subagents | CLI `multi_agent` true; collaboration tools exposed | Native developer tasks; runtime provider roles | Not exercised for this build | spawned tasks/results + runtime role checks |
| Worktrees | CLI `worktrees` true, `--worktree` help | Explicit B6 native Git demo | Not created | during-run listing and artifacts |
| MCP | CLI management commands; no deployed source server proven | Native developer tools if authorized; runtime adapter | Unverified | live folder read + scoped deployed boundary |
| Skills | Supplied SKILL file format; onboarding skill used in earlier setup | Native developer retrieval/design/release skills | New project skills authored, not invoked by Codex yet | invocation and output |
| Hooks | CLI `hooks` true; schema has Stop/SessionEnd | Native developer receipt if enabled; app outbox fallback | Example only; no hook activated | automatic event receipt + app summary test |
| Scheduled tasks | No scheduling surface proven in this chat | Optional native audit; runtime DB worker | Unverified | actual configured/fired task; worker due proof |
| Memory | CLI `memories` false | Optional native developer memory; DB app history | Native disabled; app not built | safe native proof if later enabled; DB restart proof |
| Image input | Tools available; supplied design image and actual screenshots inspected | Native developer critique; runtime vision adapter | Template screenshots captured/inspected; app vision unrun | clear/blurry runtime tests |
| Voice | CLI realtime feature flag true; client interaction untested | Optional native Codex voice; app browser speech+typing | Unverified | client-native proof separate from app exchange |
| Review | `codex review` command available | Independent native code review | Unrun | reviewed release diff + finding disposition |
| CLI / SDK | `codex exec` present; SDK not installed/probed | Bounded tooling/optional runtime experiment | Help only | supported sandboxed invocation |
| Cloud environment | Existing empty checkout/Git read works | Tested install/start draft after application implementation | Dashboard validated outside checkout | backend/frontend startup validation + confirmed draft save |
| Browser validation | Chromium + Playwright available | Functional/visual/accessibility automation | Template viewport and drawer smoke passed | complete application journeys |

No row means the deployed learning application works today. Native/partial/fallback marks for submission must be derived from actual execution artifacts, not planned files. Keep evidence synthetic/redacted.

Revision 2 targets ten-language UI/study/runtime speech and managed Drive create/upload plus folder drops. These new app capabilities are unimplemented/unverified at package stage; existing template checks do not validate them. Runtime matrix L01–L05/D01–D06 and real OAuth/STT/TTS results must be recorded before release claims.

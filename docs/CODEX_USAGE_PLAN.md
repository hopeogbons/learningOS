# Codex usage plan: cover relevant capabilities with proof

The original design lists nine feature families. This plan covers all nine and additional capabilities that help this build: project instructions, cloud setup, independent review, browser testing, image-based visual critique, resumable execution, CLI/SDK experiments, CI and controlled publication. "Use everything" means assess every relevant capability and exercise supported ones meaningfully; it does not mean claim unavailable tools or add infrastructure solely for a score.

## Development versus deployed runtime

| Feature | Meaningful Codex use while building | Deployed application boundary | Required proof |
|---|---|---|---|
| Subagents | Planner coordinates; backend/frontend implement disjoint work; Quizzer makes fixture sets; Reviewer audits | Learning roles run through `app/llm.py`; reuse role contracts, not privileged developer sessions | Actual spawned-agent tasks/results, cited artifact and independent review |
| Git worktrees | Two synthetic topic quiz artifacts in scoped branches after baseline commit | Runtime jobs/tenant transactions isolate learner work; no per-learner Git checkout | Worktree list during execution, branch/artifact diff, tests; user explicitly authorized demonstration |
| MCP | Probe tools and use an authorized scoped source connection; optional testing MCP | Runtime source adapter needs own authenticated route and deployed MCP server or honest direct API fallback | Exact tools, scoped live call, source IDs/status without credential values |
| Skills | Use retrieval-practice, design-fidelity and release-readiness SKILL.md files | Runtime prompts/schema are versioned app resources; don't assume SDK automatically discovers developer skills | Skill invocation plus output/schema checks/screenshot review |
| Hooks | If supported/trusted, a Codex Stop hook writes a sanitized developer receipt | App `session.finished` outbox triggers private Reviewer summary; distinct event namespace | Native hook activation/trust and automatic receipt; app summary separately tested |
| Scheduled tasks | If product exposes it, native Codex recurring audit checks synthetic due output/build status | Production worker computes/dispatches real review/sync jobs; native automation not relied upon for uptime | Actual configured task + fired run; nonexistent cron command is not proof |
| Memory | Inspect native feature status; store safe developer project conventions if enabled/supported | Learner weak spots/knowledge graph stay in private DB | Native developer memory evidence separately from DB restart test |
| Image inputs | Inspect supplied screenshots/fixture photos using a available native image tool | Real vision-capable API call extracts photo notes, source validation | Native developer image critique plus independent runtime photo proof |
| Voice | Exercise native Codex conversation only if available on the selected client | Ten-language browser/server STT/TTS with verified capability matrix and typing fallback | Native session recording if available; app three-turn recording separately labeled |

## Additional relevant capabilities

AGENTS.md guides every batch; cloud environment install/start instructions preserve tested setup; plan/state/log make long tasks resumable; built-in shell/browser validation tests real UI; Codex review audits authentication, tenant isolation, learning correctness and visual drift; current docs/search or official repository sources verify version-sensitive setup; draft PR/diffs provide reviewable code; CLI `exec` and JSON output can automate later offline quality tasks; SDK is a conditional experiment for a bounded runtime agent, not required production infrastructure; CI can run tests and optionally a least-privilege Codex review when authorized. App connectors/plugins are considered only for concrete source/testing needs; do not install unrelated integrations or invoke mail sending.

## Capability verification procedure

1. Record client surface, version, date and safe tool names. CLI commands: `codex --version`, `codex --help`, `codex features list`, `codex mcp --help`. Inspect configured MCP metadata only; avoid echoing URLs/env values that could contain credentials.
2. Consult the installed CLI help/config schema and current official docs. Canonical entry: https://developers.openai.com/codex/ ; guides for skills, MCP, subagents, worktrees, automations, SDK and AGENTS. This preparation's proxy blocked that domain; official GitHub `openai/codex` README and `codex-rs/core/config.schema.json` were accessible. Captured schema and hash in validation are fallback source evidence, not proof every feature activates on this client.
3. For custom role layers, schema-validate the provided `.codex/config.toml` and agent files against the installed version's schema, inspect loaded roles, invoke a harmless fixture task. CLI role configuration may not apply to cloud's own agent orchestration; use actual cloud tools where available and label the surface.
4. For hooks, the inspected official schema lists `SessionStart`, `SessionEnd`, `Stop`, `SubagentStart/Stop`, tool/permission/compaction events. These refer to Codex lifecycle, not a learning session. Use the supplied **disabled example** only after review and normal trust activation; never bypass hook trust. Trigger a supported event and inspect the receipt. Don't claim that manually calling the hook helper demonstrates an automatic event.
5. For automations and memory, check the selected client UI/tool surface. CLI flags do not establish an available scheduling UI or a writable per-learner memory API. Native memory was disabled in the inspected CLI. Record supported fallback rather than enabling features blindly. Cloud live processes don't survive environment snapshots: register startup, not a perpetual process assumption.
6. For MCP/voice, verify actual tools/browser support/consent; tools available in a developer chat don't imply the deployed server can call them. Ask only for missing scoped access; complete contract/UI work independently.
7. Update `docs/capabilities.md` with `availability`, `implementation` (native/partial/fallback), `verification` (configured/exercised/passed/failed/unverified), official source, evidence file and limitations. Preserve developer and runtime rows separately. Unknown remains unknown.

## Native evidence priorities

High-value: real subagent implementation/review, reused skills, image-guided fidelity, scoped MCP source proof, isolated worktree contribution, cloud setup and actual test/review traces. Optional client-dependent: hooks, recurring Codex automation, native memory and native voice. A real app fallback remains useful, but is not relabeled native for judging. Do not optimize feature counts at the expense of a dependable learning loop.

Revision 2 adds useful independent localization/RTL review and Drive scope/idempotency audit tasks. Codex can extract catalog keys, generate translation/evaluation candidates, inspect screenshots by locale, and test both ingestion paths; meaningful native/proficient review still verifies translation/voice correctness. Drive write permission comes from learner runtime consent, not a developer agent capability. See INTERNATIONALIZATION and DRIVE_INGESTION; native Codex voice/MCP remain separate from deployed speech/Drive adapters.

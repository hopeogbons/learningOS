# Batch 10: Turn-based voice teach-back in the existing Study card


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, Andela green palette from UI_CONTRACT (emerald #40c15f, kale #173b3f, green black #132128, opal #b0d6cd), 264px desktop sidebar, 992/1400 breakpoints, green mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Implement Voice shortcut to /study?mode=voice using browser recognition/synthesis when supported and typing otherwise. Keep the same grading path as text; record transcript text privately, allow edit before submit, require confidence before verdict and stop recording/speech on navigation. Three learner turns maximum per teach-back exchange, targeted cited Socratic follow-up about the missed idea, not a generic response. Don't infer guessing from speech hesitation alone. Mic permission denial/unsupported browser/network failure show clear typing fallback. No retained raw audio by default; disclose browser vendor processing.

Native Codex Voice may be a developer-client capability but does not make browser voice native. Exercise a native client only if actually available and record separately; app voice remains labeled browser/runtime. A verified server speech adapter supplies missing browser-language capabilities when needed to satisfy the ten-language spoken target; typing still works independently of speech access.

Dashboard-specific UI: original red Mic tile launches voice mode within same shell, white Study card, confidence/citation controls and mobile bottom nav. Speaking/listening/processing controls use accessible status text, visible stop button and transcript; muted feedback and original accents retained. Test typing fallback automatically; manually verify real supported-browser three-turn exchange with sound, transcript correction, targeted follow-up and saved event. Screenshots plus manual recording proof are required for a voice claim; headless API availability isn't microphone proof.


## Done when

F20 typing and state tests pass; real voice proof recorded or precisely blocked; UI/persistence consistent with text.

## Useful delegation

Browser speech/UI contributor; role follow-up evaluation and independent accessible-state review.

## Revision 2 batch work

Implement ten-language recognition/synthesis capability matrix, explicit selected locale/voice, browser inventory discovery and real server STT/TTS fallback when browser lacks target language. Add session-owned transient /speech/transcribe and /speech/synthesize endpoints through app/llm.py. No English audio mislabeled another locale. Verify transcription/meaning, transcript edits and three-turn cited spoken exchange per advertised language; typing on mic denial/outage. Add Arabic/multiscript screen/status review.

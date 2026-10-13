---
name: retrieval-practice
description: Generate five citation-grounded recall, explain-back and application questions from a selected Learning OS title.
---

# Retrieval Practice


1. Read docs/PRODUCT_SPEC.md and contracts/quiz-set.schema.json. Accept title/chunk ID, concept IDs, allowed citations and their extracted excerpts; reject absent/foreign source context.
2. Cover the title's critical concepts. Produce five questions with at least one recall, explain and apply item. Each tests one clear idea and carries valid concept/citation refs. Do not reveal expected answers in question wording.
3. Keep expected_answer/rubric private. Use only supplied source text; if there is insufficient material, report needs-attention instead of inventing claims.
4. Validate JSON against the supplied schema and confirm every locator/excerpt resolves. Output the quiz set plus any source uncertainty. The schema permits private answer fields; runtime public responses must strip them.
5. Run the existing relevant offline question/source tests when available and report real results. Save only synthetic fixture sets to Git. A manual JSON example does not prove Codex invocation.

Revision 2: read docs/INTERNATIONALIZATION.md and DRIVE_INGESTION.md. Verify localized output/RTL/source preservation and correct-folder UI/drop convergence when relevant; missing live proof stays blocked. All ten requested speech capabilities and actual scoped Drive writes need separate evidence.

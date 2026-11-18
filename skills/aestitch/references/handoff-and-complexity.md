# Cross-model design handoff and engineering change control

## Contract states

- **Draft**: a proposed art direction with incomplete implementation evidence. The coding agent may prototype but must not assert the design is user-approved.
- **Approved**: the operator asserts the user explicitly approved a specific screenshot/prototype; contract includes SHA-256 reference to that image and approval note. The CLI cannot independently verify user consent.
- A change to an approved direction must be proposed as a new revision rather than silently overwriting the existing contract JSON.

## Required handoff packet

1. Page purpose, information hierarchy, audience, content to present.
2. Reference IDs with concrete observations, not just design adjectives.
3. Approved design evidence (rendered screenshot/prototype if available), spacing/type/color tokens, responsive states, meaningful interaction states, and motion purpose.
4. Allowed implementation scope and explicitly forbidden redesigns.
5. Acceptance tests: actual browser screenshots at fixed viewports, keyboard focus, mobile overflow, build status, and any motion/interaction checks.

If information is missing, implement conservatively and state which visual elements were approximated. Don't assert pixel-perfect fidelity based on a prose handoff.

## Change budget review

1. Run `scope snapshot` **before** code edits; use a unique task tag.
2. Choose a task-specific `--allow` path, e.g. `app/home` (project-relative). A broad unrestricted change scope defeats review.
3. On completion, run `scope check`. It hashes source files (max 2MB each), ignores generated folders and only counts new names in JS/TS package dependencies. It does **not** detect code duplication, evaluate complexity, or scan lockfiles for supply-chain risk.
4. Exceeded thresholds / out-of-scope modifications require explanation and review; they're not inherently invalid. Large feature work deserves a larger budget but still needs boundaries.
5. Run the real project's lint/build/test suite and review code diffs. This is not replaced by Aestitch.

## Context management

Load the smallest relevant packet: personal preferences related to this page, project tokens, this page contract, task scope, and recent evidence. A future retrieval engine may index references, but v0.2 uses explicit JSON and filenames to keep provenance and corrections transparent. Do not claim RAG or embeddings are implemented.

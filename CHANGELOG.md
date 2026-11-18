# Changelog

## v0.3.1 — 2026-11-18

Reliability patch. No new creative-generation or aesthetic-scoring features.

### Fixed

- `aestitch doctor` no longer crashes when the script is run directly: use an
  explicit `importlib.util` import instead of relying on an implicit module import.
- `concept render` no longer overwrites the previous observation by default. Each
  render gets a new observation ID and the concept records its observation history;
  legacy `concept-<id>` observations remain readable.
- Observation manifests now record `capture_context` and `evidence_scope`:
  viewport, reduced-motion setting and disabled screenshot animations are explicit.
  Legacy manifests without these fields are reported as `legacy/unknown` instead of
  failing.
- Experiment packets now record `skill_commit` and a schema version, and support
  `evidence[]` with an explicit evidence class. Missing fields in older packets are
  read as `not recorded`/`none` rather than raising `KeyError`.

### Hardening (release-candidate review)

- `experiment record` (CLI and Python API) rejects `user_confirmed`; user feedback is
  recorded only through `experiment review`, which now stores `source` and
  `confirmation_context`. Reports mark commits and evidence classes as **declared by
  the Agent** and always state `Identity verified: no`.
- `concept render` uses a cross-process single-writer lock and atomically reserves
  observation IDs. A concurrent render fails clearly instead of racing; a lock is
  reclaimed only when its recorded owner process is confirmed dead (age alone never
  preempts an active capture), malformed locks require explicit manual recovery, and
  release removes only the caller's own lock. Failed captures keep a `status: failed`
  manifest and the latest-success pointer is only updated after a complete capture.
  Long Concept IDs that truncate to the same prefix now include a short hash.
- Reading a packet validates field types and raises a readable
  `Experiment schema error` instead of `AttributeError`/`TypeError`. Evidence paths are
  re-checked against the project root on every read (absolute paths, `..` escapes and
  out-of-root symlinks are `invalid_path` and are never read); status distinguishes
  `present`, `missing`, `changed`, `unreadable` and `invalid_path`.
- Duplicate evidence declarations are rejected; the same file may still be cited with
  different classes or claims.
- Documentation tests now parse fenced `aestitch ...` examples for real argument
  validity instead of only checking command names.
- Creative Guidance: hypothesis/direction/question counts are explicit defaults, not
  limits; screenshot predictions are distinguished from observed eye movement;
  open-ended exploration is allowed alongside falsifiable engineering hypotheses; and
  internal evidence states have a plain-language translation table.

### Documentation

- Added the v0.4 Creative Guidance protocol draft and minimal intent/direction/
  feedback JSON examples.
- Documented the Experiment Handoff command in the English README.
- Added a lightweight documentation/CLI command consistency test.
- Clarified Claude Code and Codex Skill installation paths.

## v0.3.0 — 2026-11-18

- Reference Observatory, Art Direction Lab, fidelity comparison and region-aware
  visual guard.
- Contextual taste comparisons with absolute acceptance and relative preference.
- Experiment Handoff packet (`experiment record/review/report`).

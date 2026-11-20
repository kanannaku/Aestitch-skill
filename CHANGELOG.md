# Changelog

## v0.4.0 — 2026-11-19

Feature and documentation alignment release candidate. Version declarations in
`pyproject.toml`, the CLI, Skill metadata and README examples are unified at 0.4.0;
this entry does not imply a tag, commit or publication.

### Added

- Rendered readability gate: `observe capture --check-text-contrast` measures rendered
  text against resolved backgrounds and writes `text-contrast.json` / `.md` per
  observation. `observe report --require-text-contrast-pass` exits 2 unless the
  observation completed, every expected viewport has current evidence, and all measured
  text passes.
- Conservative background resolution: solid and alpha-composited colours are measured;
  images, gradients, filters, backdrop filters, blend modes, opacity groups and
  `background-clip:text` return UNKNOWN. An opaque child panel still returns UNKNOWN
  when an ancestor opacity, filter or blend effect composites the subtree.
- Native `input[type=submit|reset|button]` value text is measured. A submit/reset
  without a value is measured as the browser default label; hidden controls are
  skipped.
- Composition-Aware Iteration protocol in `design-method.md`, with matching guidance in
  `feedback-method.md` and a handoff field in `visual-handoff.md`.
- Expanded Creative Guidance protocol (documentation only): triage, falsifiable
  hypotheses, two directions, preference elicitation and a plain-language evidence
  table. It adds no `intent`, `direction` or `feedback` CLI commands.
- Worked composition-iteration example in `examples/design-review/`.

### Fixed

- Added the missing `aestitch_experiments` module to the packaged `py-modules`, so an
  installed build can run `aestitch experiment` instead of raising `ImportError`.
- Readability gate integrity: a failed or unfinished observation can no longer pass;
  missing expected viewports, missing/unreadable/foreign evidence and
  manifest/evidence mismatches are blocked with a reason.
- `observe --overwrite` clears only the known text-contrast artifacts of that
  observation before writing new evidence; an old PASS is never reused as current.
- Coverage boundary: ancestor opacity, filter or mix-blend-mode above an opaque child
  background now returns UNKNOWN instead of measuring it as if the compositing effect
  did not exist.

### Documentation

- Version identity unified at 0.4.0 (`pyproject.toml`, CLI `--version`, SKILL metadata
  and README examples).
- English and Chinese READMEs describe the readability gate, composition-aware
  iteration and the real coverage limits.
- `examples/design-review/` is documented as a fictional worked example, not a
  template or an approved design.
- `SKILL.md` and the Creative Guidance reference point to repository example files by
  path instead of relative links, so a copied Skill folder has no cross-directory links.
- README now states that the Python package installs the CLI modules only; Skill
  files, references and examples are distributed through the repository/Skill folder.

### Packaging

- License metadata now uses the SPDX expression `MIT` with `license-files = ["LICENSE"]`;
  the deprecated TOML license table and MIT classifier were removed. Building requires
  `setuptools>=77`. Runtime dependencies and modules are unchanged.

### Known limitations

- Readability covers the initial static load at captured viewports only.
- Complex backgrounds are UNKNOWN; Shadow DOM, Canvas, SVG, iframe, pseudo-element text
  and non-button form controls are not measured.
- No screenshot pixel sampling for contrast and no automatic aesthetic score.

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

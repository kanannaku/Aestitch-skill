# Aestitch evaluation protocol (proposed, not yet completed)

This document specifies experiments; it does **not** demonstrate higher design quality.

## Separate the questions

1. **Creative divergence:** same content and model, no Skill versus Aestitch versus an established front-end Skill. Are the independently rendered initial concepts structurally and experientially distinct? Compare blind screenshots, real interaction, and geometry; never rely on an LLM's own beauty score.
2. **Reference observation:** did the agent actually inspect screenshots, mobile states, and key interaction states? Mark unavailable sites as unobserved, and separate evidence from agent hypothesis.
3. **Preference discovery:** allow user to reject both but prefer one relatively. Test whether later recommendations align with held-out preferences, using multiple design tasks, not training/test on same examples.
4. **Design-to-code handoff:** give agents the same approved prototype, screenshots, anchors and interaction spec. Measure missing elements, landmark mismatch, responsive behavior and semantic interactions; record what was intentionally changed.
5. **Design guardian:** run several identical iteration tasks, compare preservation of locked decisions, number of user corrections, new dependencies/files and build/test stability.

## Run controls

Record model/version, thinking effort, original code revision, tools, time/token budget, task, reference assets, screenshots (both viewports), acceptance/relative preference, design revision counts, scope report and failures. Blind the user to experimental group when possible. Repeat on more than one task and user before generalizing.

## Ratings and provenance

- The CLI records geometry and pixel change, **not art direction quality**.
- User opinions may conflict across content types; preserve context.
- A successful interactive prototype does not mean that the overall aesthetic is approved.
- Do not cherry-pick screenshots or hide the cost of manual intervention.
- Only publish images, recordings, designs or page sources with proper permission.


## Two-role experiment handoff

**Canonical Skill maintainer:** reads evidence, judges which shortcomings are supported, changes Skill source, runs regression and publishes. **Local test Agent:** runs the assigned controlled test in an isolated worktree and returns reproducible evidence. These roles must not be conflated; the test website is an instrument, not the product.

Use `aestitch experiment record` to register a test with Agent/model/Skill version, Skill commit, task, reported outcome and existing local evidence. Pair each `--evidence` path with an `--evidence-class` (`observed`, `measured`, `inferred`, `unverified`) so the packet keeps provenance explicit; an Agent may not record `user_confirmed` — that class is reserved for `experiment review`. `--artifact` is a legacy alias that records files as unverified. `aestitch experiment report` includes file integrity hashes, marks the commit and evidence classes as declared, reports each file as `present`/`missing`/`changed`/`unreadable`/`invalid_path`, re-checks that evidence paths stay inside the project, and keeps an explicitly unreviewed user verdict until feedback is supplied. The user can forward the packet and screenshot files to the maintainer. `experiment review` records the user's words, source and context, requires explicit confirmation, preserves the first confirmed review instead of silently rewriting it, and never claims identity verification.

### Minimal evaluation decision

1. **Evidence incomplete:** screenshot, interaction state or task constraints missing; ask local Agent for specific evidence rather than invent a design diagnosis.
2. **Engineering issue:** errors, regression, responsiveness or inaccessible interaction demonstrably failed.
3. **Creative direction issue:** user explicitly rejects both despite successful code tests; return to macro exploration, don't convert a relative preference into approval.
4. **Skill issue hypothesis:** failure repeated under comparable controls and sourced to a concrete Skill instruction or missing process. Improve that instruction and run a follow-up controlled comparison.
5. **Unresolved attribution:** model ability, poor reference access, coding environment, time budget or Skill may be responsible. Avoid causal claims without controls.

Use the user's exact feedback, including `neither` or `unsure`; geometric divergence cannot stand in for aesthetic approval. Do not auto-copy experiment artifacts to GitHub or promote them into global taste memories.

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

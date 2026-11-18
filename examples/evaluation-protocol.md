# Evaluating Aestitch against alternatives (planned benchmark protocol)

This is a **protocol**, not measured evidence of superiority. Do not publish an unrun benchmark as a result.

## Controlled groups

- A: same coding agent, no design skill
- B: same coding agent, a selected general front-end design skill
- C: same coding agent, Aestitch v0.2 workflow + the same actual reference artifacts

Use the same task content, initial source revision, dependencies, viewport sizes, and tool/time budget. If the groups are sequential, randomize task order and blind the reviewer to group labels. Save the model/tool versions and prompts.

## Tasks and metrics

1. Preference discovery: collect 3–5 contextual A/B choices; evaluate predictions on **held-out** tasks by human choice, not model self-rating.
2. Reference reconstruction (on owned/authorized designs): screenshot comparison plus layout/text/asset fidelity and manual responsive/interactivity review.
3. Five changes to the same page: preservation of approved decisions, subjective preference in a blind review, number of corrections.
4. Code change control: unexpected file/dep changes, warnings, build/test results, token cost and time used.

Pixel difference is a change metric, **not** a beauty metric. Record failures and do not cherry-pick screenshots. Include limits such as user subjectivity, order effects, dynamic content, unstable fonts and differing model strengths.

## Suggested record format

Store one JSON per independent run using fields: `task_id`, `group`, `model_version`, `prompt_revision`, `initial_commit`, `artifact_paths`, `user_preference`, `revisions`, `build_passed`, `scope_review_reasons`, `time_seconds`, `notes`. Only publish materials with permission.

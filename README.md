# Aestitch

**Discover your taste. Translate inspiration. Preserve design intent.**  
*Local-first design intelligence for coding agents · by Suatlora*

> **v0.2.0 early preview.** Runnable CLI + portable `SKILL.md`, not an autonomous design model. It does not browse reference URLs, judge beauty, learn visual features from pixels or guarantee that generated code reproduces screenshots.

AI coding agents can make a page work while losing its visual intent across iterations. Aestitch helps preserve **explicit user decisions**, **reference provenance**, **cross-model design contracts**, and **browser/code change evidence**. It intentionally permits multiple stylistic preferences depending on context.

## What works

| Workflow | Commands | Actual behavior |
|---|---|---|
| Personal taste | `record`, `brief`, `taste compare/report` | Stores explicit contextual choices including `both`, `neither`, `unsure`; no implicit taste inference |
| Reference library | `reference add/list` | Records URLs without fetching; copies trusted local image references privately |
| Design handoff | `contract create/show/approve` | JSON design contracts + human-readable Markdown; explicit confirmation flag + in-project image hash required for approval |
| Visual evidence | `capture`, `guard` | Playwright browser desktop/mobile captures and Pillow image differences; not aesthetic quality scores |
| Change budget | `scope snapshot/check` | Detects changed/add/removed source files, out-of-scope paths, new JS package dependency names; review flags, not code metrics |
| Tooling | `doctor` | Reports optional dependencies |

All project state defaults to `<project>/.aestitch/`, with a nested `.gitignore`. No external model API, sign-up or telemetry. Aestitch does not change website source by itself.

## Install

Python 3.10+ is required. Optional Playwright and Pillow provide screenshots/diffs. From **this repository**:

```powershell
uv sync --extra all
uv run python -m playwright install chromium
uv run aestitch doctor
```

Or run the script without packaging: `python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py --root F:\Projects\example init` (first `pip install pillow playwright` only if you need visual operations).

## Reproducible end-to-end example

Run commands from **the target website project root**, with the Aestitch CLI accessible as `aestitch` (or prefix each command with `python PATH_TO_AESTITCH/.../aestitch.py`).

```powershell
aestitch init
# Metadata only; URL is not fetched or visually analyzed
 aestitch reference add --label "Editorial source" --url "https://example.org" --focus typography --context homepage
 aestitch reference add --label "My screenshot" --image ".\approved-capture.png" --focus composition
 aestitch reference list
# Use the returned reference IDs instead of placeholders.
 aestitch taste compare --left ref-FIRST --right ref-SECOND --choice both --why "Each suits a different module" --context homepage
 aestitch taste report
 aestitch contract create --page home --goal "Present my work" --direction "Editorial, deliberate, cinematic" --scope "app/page.tsx" --reference ref-FIRST
 aestitch contract show --page home
# Only after the user explicitly accepts a real, local prototype image:
 aestitch contract approve --page home --evidence ".\approved-capture.png" --note "User approved this composition" --user-confirmed
 aestitch scope snapshot --tag home-redesign
# Start the project's dev server, capture original before edits:
 aestitch capture --url http://127.0.0.1:3000 --tag baseline
# Implement scoped changes, run tests, then:
 aestitch capture --url http://127.0.0.1:3000 --tag candidate
 aestitch guard
 aestitch scope check --tag home-redesign --allow app/page.tsx --max-added 0 --max-changed 2 --max-deleted 0 --max-dependencies 0
```

**Important:** `--root` is a top-level argument and goes **before** `reference`, `contract`, etc. Use distinct snapshot tags per task. Screenshot baseline overwrites require explicit `--overwrite-baseline`. `scope snapshot` overwrites require `--overwrite`.

## Skill usage

Add `skills/aestitch` to your coding agent's project-specific Skill directory (`.agents/skills/aestitch` for compatible clients; actual discovery path is agent-specific). Its instructions require: observe → compare user taste → write draft contract → get explicit approval → capture/implement under change scope → review browser/code evidence → record decisions.

See [taste discovery](skills/aestitch/references/taste-discovery.md), [handoff and complexity](skills/aestitch/references/handoff-and-complexity.md), [security limitations](skills/aestitch/references/evidence-and-safety.md) and [benchmark protocol](examples/evaluation-protocol.md).

## What is NOT implemented

No automatic reference-page ingestion or screenshot semantic analysis; no preference predictor, vector database, RAG retrieval, aesthetic scoring, full static-analysis complexity detector, model orchestration or completed independent performance benchmark. Reference and taste workflows require actual user and agent reasoning. Visual evidence is for **review**, not automatic accept/reject.

## Develop and test

```powershell
python -m unittest discover -s tests -v
python skills/aestitch/scripts/aestitch.py --help
```

MIT license. The source can be used independently of the Suatlora personal website. Do not share personal screenshots or reference materials without permission.

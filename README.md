# Aestitch

**Discover your taste. Explore real art directions. Preserve design intent.**  
*Evidence-first design intelligence for coding agents · by Suatlora*

> **v0.3.0 preview:** Aestitch is a portable Agent Skill and a local Python CLI. It is **not** an autonomous aesthetic model: a human or vision-enabled agent must still interpret reference material, create concepts and judge the designs. It does not promise award-winning UI from a prompt.

## Why it exists

Vibe coding can create maintainable web pages that still feel generic. Adding more reference links or prohibitions is often not enough: an agent can lose the original visual ideas during **reference observation → art direction → prototype → code handoff**. Aestitch makes those steps explicit and testable, while retaining the memory and code-change controls introduced in v0.2.

## What works in v0.3

| Capability | CLI commands | What it really does |
|---|---|---|
| Reference Observatory | `observe capture/report` | Visits a **trusted, explicitly supplied** localhost/remote URL or renders a local offline HTML file; saves viewport screenshots, scroll frames, DOM element geometry and computed font/color facts. Remote visits require `--allow-remote`; same-host-only requests can cause missing assets. |
| Art Direction Lab | `concept add/render/compare` | Stores independently **authored** HTML prototypes, renders desktop/mobile, flags identical prototypes, repeated mechanisms and near-identical landmark geometry. Does not invent designs or rate beauty. |
| Visual handoff | `fidelity` | Compares one prototype's screenshot and anchors to a separately observed implementation at the same viewport. Reports differences, not implementation correctness or aesthetic quality. |
| Region-aware visual guard | `guard --top-viewport` | Compares first viewport of full-page screenshots even if page heights differ. Does not compare lower sections. |
| Contextual taste | `taste compare/report` | Can separately record **absolute acceptance** and **relative preference** (e.g. "neither accepted, but B is more refined"). No automatic style inference. |
| Existing controls | `reference`, `record`, `brief`, `contract`, `scope`, `capture`, `doctor` | Local reference metadata, explicit preference memory, draft/approved design contracts, source-change budgets and screenshot baselines. |

All project evidence is kept in `<target-project>/.aestitch/` and ignored by git by default. No login, external model API, vector database or telemetry is required. Aestitch itself does not modify the website source.

## Install / update (Windows PowerShell)

**Existing users (v0.2)** should pull new code rather than reclone the repository:

```powershell
cd F:\Projects\Aestitch-skill
git pull --ff-only
uv sync --extra all
uv run python -m playwright install chromium
uv run aestitch doctor
```

If a Codex project has **a copied project-level Skill**, update that copy after verifying any local modifications:

```powershell
# Example: C group; do not overwrite hand-edited Skill files without reviewing them.
Copy-Item "F:\Projects\Aestitch-skill\skills\aestitch\*" `
  "F:\Projects\aestitch-lab-c\.agents\skills\aestitch" -Recurse -Force
```

If you have not cloned yet, clone `https://github.com/kanannaku/Aestitch-skill` first. Python >=3.10 is required. Playwright/Chromium supports browser capture; Pillow supports image evidence. You can run `uv run --project F:\Projects\Aestitch-skill aestitch --root F:\Projects\YOUR-PROJECT ...` from anywhere. **The `--root` flag comes before the subcommand.**

## What the demo actually renders

These are real Chromium screenshots of two **small, original, self-contained concepts**, not AI beauty predictions. They intentionally vary their mechanism and composition; a user may reject both.

| Computational space (spatial research) | Editorial object (typography-first) |
|---|---|
| ![Dark spatial graph prototype screenshot](examples/creative-lab/preview-spatial.png) | ![Warm editorial prototype screenshot](examples/creative-lab/preview-editorial.png) |

## Quick experiment — original creative directions

Aestitch ships two **demonstration prototypes** that intentionally use different mechanisms, not just different colors. They are examples to exercise its evidence pipeline; they are not recommended UI templates.

From the Aestitch repository directory:

```powershell
uv run aestitch init
uv run aestitch concept add --id spatial --title "Computational space" --thesis "Research as navigable space" --mechanism "Interactive node graph" --html-file examples/creative-lab/computational-space.html
uv run aestitch concept add --id editorial --title "Editorial object" --thesis "Research as a printed object" --mechanism "Oversized typography and sampling" --html-file examples/creative-lab/editorial-object.html
uv run aestitch concept render --id spatial
uv run aestitch concept render --id editorial
uv run aestitch concept compare --left spatial --right editorial
```

Outputs: `.aestitch/observations/concept-spatial/`, `.aestitch/observations/concept-editorial/` and `.aestitch/reports/concept-spatial-vs-editorial-desktop.json`. If running again, use a new concept ID; registration never overwrites an earlier idea.

## Observe an actual web page

From a **target website project** whose dev server you have started on localhost:

```powershell
uv run --project F:\Projects\Aestitch-skill aestitch --root F:\Projects\aestitch-lab-c observe capture --id my-home --url http://127.0.0.1:3000 --viewport both --steps 3
uv run --project F:\Projects\Aestitch-skill aestitch --root F:\Projects\aestitch-lab-c observe report --id my-home
```

Only explicitly trusted external references may be sampled with `--allow-remote`, and resource restrictions can result in incomplete rendering. A complex WebGL/scroll/hover site still needs a **manual browser interaction and recording**; the CLI captures static frames and computed CSS/geometry, **not the whole experience**. A metadata-only `reference add --url` command never visits the page.

## Compare design handoff

After you create/choose a prototype and implement it in Next.js, observe the real implementation at the **same viewport**:

```powershell
uv run aestitch observe capture --id implemented-home --url http://127.0.0.1:3000 --viewport both --steps 1
uv run aestitch fidelity --concept spatial --observation implemented-home --viewport desktop
uv run aestitch fidelity --concept spatial --observation implemented-home --viewport mobile
# Existing baseline/candidate flow; use if full-page heights differ:
uv run aestitch guard --top-viewport
```

Use the first three commands only after registering and rendering a `spatial` concept in the **same target project**. Pixel and geometry differences do not establish aesthetic fidelity; judge the actual interactive page and explain deviations against an approved design contract. A draft is not approved.

## Architecture and trust

- Portable Skill: [`skills/aestitch/SKILL.md`](skills/aestitch/SKILL.md) and on-demand references.
- CLI modules: `aestitch.py` (commands, existing memory/guard), `aestitch_workflows.py` (memory, references, contracts and scope) and `aestitch_creative.py` (observations, concepts, fidelity).
- Web pages and supplied HTML are **untrusted**. Browser capture blocks all external subresources for offline files, and only permits same-host requests for live pages. Inline JS in supplied HTML can still run; use trusted material only.
- Design contracts require explicit user confirmation before marking approved. A CLI flag cannot independently verify human consent.
- The CLI cannot infer personal taste, inspect hidden animations or audio, automatically extract design meaning from screenshots, create original artwork, measure an aesthetic score or prove superiority over other Skills.

## Evaluation and evidence

Run `python -m unittest discover -s tests -v`. Optional real Chromium integration requires `AESTITCH_TEST_CHROMIUM=1` and a Playwright Chromium installation (or an explicit `AESTITCH_CHROMIUM_EXECUTABLE`). See [evaluation protocol](examples/evaluation-protocol.md). An earlier A/C experiment showed visual constraints alone did not produce a distinctive art direction; no formal benchmark of v0.3 aesthetic quality has been completed.

See [中文文档](README.zh-CN.md), [creative demo](examples/creative-lab/README.md) and [visual observation rules](skills/aestitch/references/observation-evidence.md).

# Aestitch

**Your taste. Your design. Every iteration.**

*A local-first design memory & visual change guardian for AI coding agents — by Suatlora.*

Many AI-made websites begin with a decent concept and drift toward generic UI during repeated prompts. Aestitch v0.1 preserves **explicitly confirmed personal taste** and captures **actual browser evidence** across iterations. It does **not** pretend to compute an objective aesthetic score.

> Early preview. The design-memory and screenshot-comparison workflows are implemented; a full autonomous creative agent and calibrated aesthetic evaluator are **not**.

## What works now

- **Remember your decisions:** record `prefer` / `avoid` feedback with a scope and render a clear design brief.
- **Protect the baseline:** capture localhost pages or self-contained offline HTML prototypes with Playwright at desktop/mobile sizes, preventing accidental overwrite.
- **Detect drift:** compare screenshots with Pillow, highlight changed pixels, report overflow and missing alt attributes, and flag large changes for review.
- **Portable Skill:** standard `skills/aestitch/SKILL.md` for compatible coding agents, plus independent scripts.
- **Local-first:** no account, API key, external model or telemetry required. `.aestitch/` is private and locally ignored by git by default.

## Quick start

Use Python 3.10+ and run from the **website project root**. Optionally, from the Aestitch repository first run `python -m pip install -e ".[all]"` to install the `aestitch` command. Replace `PATH_TO_AESTITCH` with where you placed the Aestitch repository or installed skill.

```powershell
# Optional modules. Image compare and browser capture need these dependencies.
python -m pip install pillow playwright
python -m playwright install chromium

# Minimal memory workflow (no extra packages required)
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py init
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py record --kind avoid --axis color --note "No generic indigo hero gradients" --context "homepage"
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py brief

# Start your own website separately (e.g. npm run dev)
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py capture --url http://127.0.0.1:3000 --tag baseline
# Make an intentional change and reload:
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py capture --url http://127.0.0.1:3000 --tag candidate
python PATH_TO_AESTITCH\skills\aestitch\scripts\aestitch.py guard
```

For an offline HTML prototype inside the target project, replace `--url ...` with `--html-file .\prototype.html`. Only self-contained inline CSS/resources are reliable in offline mode.

You can also pass `--root F:\Projects\your-website` **before** the subcommand when running the script from another directory. If you have a system Chromium installed, you can set `AESTITCH_CHROMIUM_EXECUTABLE` to its full executable path as an alternative to downloading Playwright Chromium. Browser capture is restricted to localhost unless `--allow-remote` is explicitly provided; do not run it on unfamiliar websites.

## Agent setup

Copy `skills/aestitch` into your project's `.agents/skills/aestitch` folder or install as a Skill from the source repo after publishing. For different clients, follow their own skill discovery path. Invoke the skill and ask:

> Read the Aestitch brief. Capture a visual baseline before editing. Preserve approved choices. Capture the candidate and explain what changed using the guard report. Do not call a screenshot diff an aesthetic score.

## Commands

| Command | Function | Requires |
|---|---|---|
| `init` | Initialize local profile and ignore rules | Python |
| `record` | Store explicit design feedback | Python |
| `brief` | Summarize accepted/avoided choices | Python |
| `capture` | Capture browser screenshots & diagnostic metadata | Playwright + Chromium |
| `guard` | Generate pixel diff and evidence report | Pillow |
| `doctor` | Check dependencies | Python |

`guard` exits with status 2 if a screenshot is missing or dimensions differ, but outputs a report. A large changed-pixel percentage is marked `needs_review`, not automatically failed.

## Important limitations

A screenshot does not test hover, keyboard navigation, all animations or accessibility. Pixel difference only detects change, not taste, artistry or UX quality. Reproducibility requires controlling fonts, data and environment. No image generation or ML-based preference learning is included in v0.1.

## Roadmap

- [x] Memory with explicit feedback and contextual scope
- [x] Local browser capture + basic diagnostics
- [x] Desktop/mobile image comparison + reports
- [ ] Interactive preference comparison from real A/B prototypes
- [ ] Screenshot regions and dynamic-content masking
- [ ] Repeatable demo benchmark against no-Skill baselines
- [ ] Rich UI critique with grounded evidence and optional vision provider
- [ ] Multi-project preference merge with explicit opt-in

## Development

```bash
python -m pip install pillow
python -m unittest discover -s tests -v
python skills/aestitch/scripts/aestitch.py doctor
```

Contributions welcome after initial public release. **MIT License**. Authored under the Suatlora personal IP; the project name and artwork are not themselves granted as trademarks by the MIT license.

# Creative Lab demonstration (not a design recommendation)

These are two **original, self-contained, local HTML prototypes** to test Aestitch's *evidence workflow*. They are intentionally structurally different: a dark, spatial research graph and a light, oversized typographic editorial object. They are **not** templates that the Skill should copy by default or proof that Aestitch designs better websites.

Both include a small interactive element and named `data-aestitch-anchor` landmarks for visual handoff checks. No remote scripts, fonts, images, or APIs are required.

Run from this repo root after installing optional Playwright/Chromium + Pillow:

```bash
python skills/aestitch/scripts/aestitch.py init
python skills/aestitch/scripts/aestitch.py concept add --id spatial --title "Computational space" --thesis "Research as navigable space" --mechanism "Interactive node graph in a two-plane hero" --html-file examples/creative-lab/computational-space.html
python skills/aestitch/scripts/aestitch.py concept add --id editorial --title "Editorial object" --thesis "Research as a collected editorial artifact" --mechanism "Oversized typography, physical folio, responsive sample bars" --html-file examples/creative-lab/editorial-object.html
python skills/aestitch/scripts/aestitch.py concept render --id spatial
python skills/aestitch/scripts/aestitch.py concept render --id editorial
python skills/aestitch/scripts/aestitch.py concept compare --left spatial --right editorial
```

Open the captured PNGs from `.aestitch/observations/concept-spatial/` and `.aestitch/observations/concept-editorial/`. Experiment states and preference observations stay private and ignored by Git.

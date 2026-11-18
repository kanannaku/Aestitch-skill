# Visual handoff contract — design-to-code fidelity

A design is not fully specified by adjectives such as "cinematic", "tech", "high quality" or "premium". Hand off a **running, self-contained prototype**, browser screenshots, observed geometry, typography, mobile layout, recorded interaction states and explicit constraints.

## Minimum handoff

- Exact prototype and desktop/mobile viewport dimensions.
- Screenshots of initial view and key interactive states; their source/path/hash.
- Observable `data-aestitch-anchor` landmarks (`hero-copy`, `primary-visual`, etc.) and positions.
- Fonts (actual load status/fallback), colors, spacing, assets and licenses.
- Intended behavior: mouse, keyboard, touch, reduced motion.
- Approved vs draft decisions, explicit ambiguities and what can change.
- Allowed source files and reasonable change budget.

## Check implementation

1. `concept render --id selected` makes a browser snapshot of prototype.
2. Start the real website and `observe capture --id candidate --url http://localhost:3000 --steps 1` in the **same viewport**.
3. `fidelity --concept selected --observation candidate --viewport desktop` compares captured viewport pixels and corresponding landmark geometry, noting overflows and errors.
4. Check mobile separately. For dynamic content and interactions, compare the same explicit UI state, not an arbitrary random frame. Video/manual browser inspection is required for motion.
5. Explain mismatch rather than silently redesigning. Similar pixels alone cannot establish good semantics or responsive layout.

All numeric differences measure **difference**, never beauty, fidelity of behavior, or user satisfaction. When moving from original prototype to a new content-rich page, compare carefully selected stable regions. Full-page screenshot differences can be misleading when content length changes.

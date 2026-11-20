# Personal design memory method

Only record explicit feedback with meaningful context.

Examples:
- User: "I prefer this asymmetrical layout to the three-column card grid" → `record --kind prefer --axis composition --note "Asymmetrical editorial grouping over uniform card grid" --context "portfolio home"`.
- User: "That purple glow looks generic" → `record --kind avoid --axis color --note "Decorative purple glow with no information value" --context "dark homepage"`.

Do not infer a stable style rule from a single screenshot or from the agent's own opinion. When repeated preferences conflict, keep both context labels and explain the tradeoff. Ask for a clarification instead of silently discarding the older preference. Profiles are user-editable, local and per-project.

## Third-party critique

Third-party reviews (another model, an external reviewer, a design-savvy friend) are **external assessments**, not user-confirmed taste. Preserve their wording and attribution. Convert each recommendation into a contextual design hypothesis; do not automatically store it as a universal preference or approved design constraint.

An external review may legitimately trigger analysis, a diagnostic prototype or an experiment without first being confirmed by the user. What it must not do is become the user's preference or an approved design constraint without the user's own confirmation.

Before acting on a review, separate:

- `observed` — visible in the supplied screenshot or render;
- `measured` — a browser or DOM measurement;
- `external_review` — the reviewer's judgement or recommendation, attributed;
- `agent_hypothesis` — the Agent's interpretation or proposed fix;
- `user_confirmed` — only what the user actually accepted, in their own words.

A review can identify a real observable problem and still propose a rule that is wrong for this project. Do not encode “never center images”, “no repeated sections”, “exactly two font weights” or similar global bans from a single critique. Ask which elements and relationships the criticism refers to, and test the smallest change that addresses it. If the user relays a review, it remains external input until the user says they agree with it.

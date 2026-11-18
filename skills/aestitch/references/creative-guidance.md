# Creative Guidance — v0.4 protocol preview

Status: **protocol draft for v0.4**. It defines how an Agent should guide a user who cannot describe design in professional language. It does **not** add new CLI commands in v0.3.1, and it does not make Aestitch an aesthetic scorer.

The product goal is narrow:

> Help a non-designer explore different directions, recognise what they personally like, and keep a distinctive result through implementation — without pretending that a tool can decide whether the design is good.

Aestitch's CLI records facts. The Agent interprets, proposes and critiques. The user decides what they like and what is approved.

---

## 1. Responsibilities

| Actor | Owns | Must not do |
| --- | --- | --- |
| Aestitch CLI | Local evidence, hashes, browser capture, files, contracts, scope, experiment packets | Infer taste, generate art direction, score beauty, approve on the user's behalf |
| Agent | Translation, questions, hypotheses, direction cards, prototypes, evidence-based critique | Present its own preference as the user's, rank directions as objective truth, turn one reaction into a permanent rule |
| User | Personal preference, acceptance/rejection, relative preference, final approval | Being forced to learn design vocabulary or answer an endless questionnaire |

A preference is evidence about **this project and this context** until the user explicitly says otherwise.

---

## 2. Triage before changing anything

When the user says “普通”, “像 AI 做的”, “说不上来哪里不对”, the Agent first classifies the problem:

| Type | Typical evidence | First action |
| --- | --- | --- |
| `local` | A specific type, spacing, contrast, copy, focus or feedback issue can be named | Fix at the lowest sufficient level; keep the structure |
| `direction` | No nameable core idea; the structure is interchangeable with a template; changing colours/fonts leaves the same thing | Revisit direction cards; do not polish the same skin |
| `unsure` | The user feels something is wrong but cannot locate it | Build one small comparison that isolates one variable |
| `regression` | “上一版更好，这一版变难看了”; an approved design was damaged by a later change | Compare against the confirmed baseline and restore it |

Record the triage as a hypothesis, not a verdict:

```json
{
  "triage": "local | direction | unsure | regression",
  "because": ["specific observable evidence, not a feeling"],
  "would_change_my_mind": ["what new evidence would make me reclassify"],
  "user_words": "verbatim"
}
```

The user may overturn the classification at any time. Do not show the user a taxonomy quiz; the labels are for the Agent's reasoning and for the record.

A `local` problem that is fully specified does not need a hypothesis list: fix it, show the result, and keep the change reversible. Hypotheses exist to help locate an unclear problem, not as paperwork for obvious fixes.

---

## 3. Hypotheses, not adjectives

A vague complaint may become at most **three falsifiable hypotheses**. Three is an efficiency default, not a quota: one precise hypothesis is better than three vague ones, and an open-ended creative exploration may legitimately have no single-variable test.

Two modes must stay distinct:

- **Engineering hypothesis** — a specific, testable claim with a falsifying result (below).
- **Open-ended exploration** — the user wants to see what a direction could become. The Agent may build and show work without forcing every visual idea into a controlled experiment; it should still say what it is guessing and what the user is being asked to judge.

```json
{
  "id": "H1",
  "observation": "In the screenshot the image occupies most of the first screen; the Agent predicts the image is seen before the project name",
  "claim": "Changing the title's weight and position will make the project name the first read",
  "test": "Change only the title hierarchy; keep everything else identical",
  "falsified_if": "The user still notices the image first, or cannot name the project"
}
```

The `observation` above is a prediction from visual scale and position, not eye-tracking. Real first fixation can only be claimed after observing a real user; otherwise label it `inferred` or `taste_hypothesis`.

Rules:

- Every hypothesis is tied to a specific screenshot, anchor, text block, control or state.
- Every hypothesis states what result would prove it wrong.
- “提升高级感”, “更有设计感”, “更现代” are not hypotheses; ask what observable detail produces that impression.
- Do not run ten experiments at once. One variable per comparison unless the user asks for a broad exploration.

---

## 4. Prototype levels — use the lowest sufficient level

| Level | What changes | Cost | Use when |
| --- | --- | --- | --- |
| L0 | Tokens only: type scale, weight, measure, colour, spacing | Lowest | A local craft hypothesis |
| L1 | One component or section, including its states | Low | Hierarchy, feedback, content grouping |
| L2 | Whole-page composition: section order, first-screen structure | Medium | Page narrative or priority is wrong |
| L3 | Direction: new mechanism, new page type, new interaction model | High | The direction itself is generic |

The level is a cost guide, not a rule that forbids redesign. If the user wants a fundamentally different site, L3 is legitimate even when an L0 patch is cheaper. The decision is the user's goal plus evidence, not “always choose the cheapest edit”.

Do not default to building a complete website. A single-screen prototype that demonstrates the thesis is enough to decide whether to continue.

---

## 5. Two directions by default

Show **two** genuinely different directions first. Two are easier to compare seriously and produce more honest feedback than three. Add a third only when both fail to help the user articulate a preference, and make it differ at the mechanism level — not another colour/font skin.

Two is a default budget, not a cap. If the user asks for five concepts, show five; the Agent must not refuse or quietly collapse the request to two.

Each direction card contains:

```json
{
  "id": "direction-a",
  "one_sentence": "Turn the site into a field note that updates itself, not a portfolio list.",
  "mechanism": "Entries reorder by observation date; the reader sees change, not a project index.",
  "signature_element": "Every entry has an expandable 'reading for that day'.",
  "tradeoff": "No conventional navigation; first visit needs one sentence of guidance.",
  "risk": "With too little content, the page feels empty.",
  "intent_fit": ["desired_response: the work feels ongoing", "audience: non-specialists"],
  "not_this": "Not a dark page with fluorescent green 'tech' styling."
}
```

No ranking, no score, no “recommended”. State trade-offs instead: “A depends more on content volume; B is easier to make work on the first screen.”

---

## 6. Intent, not a style questionnaire

Ask at most six questions, one at a time. Six is a default budget, not a limit on the user's request: stop as soon as the Agent has enough to act, and never run a questionnaire the user has already answered elsewhere:

1. Who is this for, and what are they doing now?
2. After visiting, what should they do or remember?
3. What three feelings should the site leave? (Contradictions are allowed.)
4. What is one thing you immediately like — a site, poster, book, shop, game, object? What specifically do you like about it?
5. What is one thing you immediately dislike? What specifically?
6. What constraints cannot change?

Write the answers to `intent.json` (see `examples/creative-guidance/intent.example.json`) and read them back to the user:

> “I hear: the site should feel quiet but not empty; visitors should understand the material research within 30 seconds; you dislike rounded SaaS cards; the existing logo stays.”

The user confirms **“is this what I meant?”**, not **“is this design good?”**.

Taste anchors use `like` / `dislike` / `mixed`, and each anchor records the specific feature, the user's exact words, and `scope: "project"`. “I like that site” is not permission to copy its palette.

---

## 7. Evidence-based critique

Critique each prototype on fixed dimensions, without scores:

| Dimension | Question | Evidence |
| --- | --- | --- |
| Intent fit | Does it serve the confirmed goal? | intent entries + page structure |
| Hierarchy | What is seen first, second, third? | screenshot / anchor geometry / text order |
| Legibility | Is key text readable on desktop and mobile? | font size / contrast / line breaks |
| Interaction honesty | Does the claimed mechanism actually exist? | state screenshots / timing / code |
| Identity | What specific thing might the user remember? | signature element |
| Content fit | Does it read like this project, not a template? | real text/data |
| Accessibility | Keyboard, focus, contrast, reduced motion | measured facts |

Every critique item is labelled:

- `observed` — visible in a screenshot, code, or measurement;
- `inferred` — the Agent's explanation;
- `taste_hypothesis` — the Agent's guess about the user's preference, which only the user can confirm.

Do not write “more premium”, “more modern”, “not beautiful enough”, star ratings, or rankings.

### Speaking to the user

Internal evidence labels are for the record, not for the user's screen. Translate them into plain language, and never upgrade an `inferred` or `unverified` state into a fact:

| Internal state | Say instead |
| --- | --- |
| `observed` (screenshot/DOM) | “In this render, the heading is …” |
| `measured` | “The gap measures …” |
| `inferred` | “I think this is because … — that's my guess.” |
| `unverified` / `not_observed` | “I haven't checked how this behaves when you hover/click/use the keyboard yet.” |
| `interaction: unverified` | “这版动效还没有经过实际操作检查。” |
| `user_confirmed` recorded in a review | “You said …; I've recorded it as this project's feedback.” |
| `taste_hypothesis` | “I'm guessing you may like …; only you can confirm it.” |

---

## 8. Preference elicitation — help the user discover a judgement

When the user says “两个都不是很喜欢，但第二个好像更有感觉”, do **not** immediately record “the user likes direction B's font and colour”. Ask one low-burden follow-up:

> “Is it the overall sense of space, or the way it changes when you interact?”

If the user still cannot say, do not keep asking terminology questions. Build a tiny controlled comparison that isolates the suspected source (space vs. motion vs. type). The goal is to help the user locate the feeling, not to turn them into a design reviewer.

The user is never required to explain a preference. “I don't know why, I just like it” is a complete answer: record it as `keep` with the user's exact words and no invented cause. The Agent's explanation stays in `agent_interpretation` and remains a guess.

Record only what the user actually said:

```json
{
  "target": "concept-b / observation-... / state-after-click",
  "reaction": "keep | change | reject | unsure",
  "element": "hero | nav | type | colour | motion | copy | layout | other",
  "user_words": "verbatim, unchanged",
  "agent_interpretation": "separate field; may be wrong",
  "scope": "project",
  "confirmed": true
}
```

Rules:

- `user_words` is verbatim; `agent_interpretation` never replaces it.
- `confirmed: true` in this example is a **recorded declaration** that the user gave the feedback. It is not identity verification, and the CLI cannot prove who operated the keyboard.
- Default `scope` is `project`.
- A single reaction does not become a global rule.
- `candidate_long_term` requires the user to say “以后都这样” or equivalent, and a second confirmation. Even then it is a candidate, not an automatic profile update.
- `unsure` and `neither` are valid outcomes.

---

## 9. Identity without gimmicks

Distinctiveness is not weirdness. It is one deliberate, content-specific decision carried through structure, type and interaction.

Useful prompts:

- “What is the one thing you would describe to a friend?”
- “If you removed everything except one element, what should remain?”
- “Does that element help the content, or is it only decoration?”

The memory question (“what do you remember after closing the page?”) is **one useful observation, not the sole acceptance test**. A memorable gimmick can still be bad design. The final test is whether the identity serves the site's content and the user's intent.

Do not claim “distinctive” on the Agent's own authority. If the user cannot name anything specific, mark identity as `unverified`.

---

## 10. Protect what was approved

After the user explicitly accepts a direction:

1. Save the exact prototype and its evidence.
2. Create or approve a Design Contract only when the user really confirmed it; a flag alone is not proof of consent.
3. Hand off the running prototype, desktop/mobile captures, observable anchors, interaction-state descriptions and the approved contract — not an adjective-heavy prompt.
4. On later changes, use `fidelity`, `guard` and `scope check` to detect drift. A working build is not an approved design; a draft contract is not approved.

---

## 11. Guardrails

- No fixed aesthetic scorer, star rating or “design quality” number.
- No forced linear questionnaire; the flow adapts to what the user can express.
- No default style (dark, minimal, Swiss, brutalist, etc.).
- No infinite questioning or prototype generation. Stop when the next decision belongs to the user.
- No automatic promotion of project feedback into long-term taste.
- No pretending a proposed v0.4 feature exists in the v0.3.1 CLI.

---

## 12. Minimal JSON examples

- [`intent.example.json`](../../../examples/creative-guidance/intent.example.json)
- [`direction.example.json`](../../../examples/creative-guidance/direction.example.json)
- [`feedback.example.json`](../../../examples/creative-guidance/feedback.example.json)

These are examples for the Agent's working notes. They are not written by the CLI in v0.3.1.

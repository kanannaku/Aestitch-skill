# Composition-aware iteration — worked example

Status: **one worked example from the single-page experiment `type-led-v3f`**, a fictional morning-swim personal site. It is not a template, a recommended layout or an approved design. The external review was written by another model and relayed by the user; it is `external_review`, not `user_confirmed` taste.

Evidence mentioned below lived in the test workspace and is not shipped with the Skill. The values are recorded to show the *kind* of evidence to collect, not to prescribe sizes or proportions.

## 1. Before-state problem

External review (`external_review`, attributed to Gemini, relayed by the user):

- The lower half still reads as a stack of similar horizontal bands: a three-column schedule row, a big-number result row, an isolated centered food photo, then a two-column people/water row.
- The centered food photo looks pasted in: it interrupts the bands but does not belong to any nearby content relationship.
- Body text and small labels are weak on the warm paper background.

Agent hypothesis (`agent_hypothesis`): the page has acceptable modules but no page-level rhythm. The problem is the *sequence*, not any single module's colour or font. This is a hypothesis about this page, not a universal rule that horizontal sections are bad.

Baseline (`observed` + `measured`): the registered `type-led-v3e` render at 1440×900 and 390×844; body 18px / 1.95, log body 17px / 1.95, person and water copy 15px / 1.9, contact paper with a yellow top rule. The hero, top pool photo, log and contact were already accepted as the page's identity by the user's earlier direction; they were treated as protected.

## 2. Related elements and neighbours

The four target modules and their neighbours:

| Module | Content role | Compositional role before | Immediate neighbours |
| --- | --- | --- | --- |
| 本周 (this week) | Recurring schedule data | Three equal columns, full-width band | 日志 above, 记录 below |
| 记录 (result) | One performance result | Big number left, copy right, full-width band | 本周 above, breakfast photo below |
| Breakfast photo | After-swim life evidence | Isolated centered inset, no text relationship | 记录 above, 池边 below |
| 池边 (poolside) | People and water conditions | Two-column list, full-width band | Breakfast photo above, contact below |

Visual-system relationships already present: paper background, cobalt data, yellow accent, three type roles (display / reading / data), thin rules. The repeated full-width header + rule was the main shared shape.

Change impact to watch:

- moving the breakfast photo into 池边 must not break the image credit or its responsive crop;
- merging 本周 and 记录 must keep both headings and all data, and keep `#week` and `#record` anchors working;
- removing the isolated photo band must not leave a blank gap or collapse the page's pacing;
- the protected hero, top photo, log and contact must not move or change their confirmed identity.

## 3. Allowed changes and the chosen hypothesis

Protected: hero identity, navigation, top pool photo, main title, existing data and copy, contact paper background with the yellow rule.

Allowed: layout relationships among 本周 / 记录 / breakfast photo / 池边; image-text composition; local media ratio; local type hierarchy; responsive arrangement.

Forbidden: new fictional records, a theme change, meaningless animation, a full component rewrite, new framework or style dependencies.

Two hypotheses were proposed:

- **A — data/life grouping**: put 本周 and 记录 together as one quantitative spread; put the breakfast photo and 池边 together as one life spread.
- **B — editorial offset**: keep the content order but vary scale and spacing to break the uniform bands.

**Chosen: A**, because the content roles already divide into numbers and life; grouping follows meaning rather than adding decoration. Only one candidate was built, as the maintainer specified.

The implementation:

- 本周 became a narrow left rail; 记录 became the wider focal column. Both headings and all data stayed.
- The breakfast photo moved into the right-hand rail of 池边, below the water temperature and above its caption. It became part of a "pool → water → after-swim" reading column instead of a standalone band.
- 池边 kept its people list on the left and its water/photo field-note rail on the right.
- Mobile stacked each spread in DOM order; the photo stayed with the water content.

## 4. Browser-observable evidence

Desktop 1440×900 (`observed` + `measured`):

- `scrollWidth = 1440`, `innerWidth = 1440` — no horizontal overflow.
- Page height 4616px (v3e: 5241px); the removed standalone photo band and merged spreads reduce total height by 625px.
- All six navigation anchors resolve; no page errors.
- Three log `<details>` elements load as `[true, false, false]`; clicking the second summary produces `[true, true, false]`. The interaction still works.
- Data spread: 738px tall. Week rail 403×532; record column 857×532. Record number 124px; record copy 18px / 2.0.
- Life spread: 837px tall. People 744×485; rail 403×628; photo 403×323. The photo is in the rail, not a separate section.
- Measured text: week note 15px / 1.95, 8.2:1; record copy 18px / 2.0, 10.58:1; person copy 15px / 1.9, 8.75:1; water copy 15px / 1.95, 9.94:1; photo credit 9px, 5.93:1.
- All measured text styles on the paper background meet the 4.5:1 baseline for normal text. This does not include hero text over photography or the protected top-photo caption.

Mobile 390×844 (`observed` + `measured`):

- `scrollWidth = 390`, `innerWidth = 390` — no horizontal overflow.
- Page height 5101px; data and life spreads stack in DOM order; the photo remains with the water content.
- Measured text: week note 14px / 1.9, 8.2:1; record copy 15px / 1.95, 10.58:1; person copy 14px / 1.85, 8.75:1; water copy 14px / 1.9, 9.94:1; photo credit 9px, 5.93:1.

`concept compare --left type-led-v3e --right type-led-v3f` (`measured`):

- Mean normalized geometry change: 0.0946.
- Changed anchors: `h2-2` 0.1653, `h2-3` 0.225, `h2-4` 0.3264; sections 3–5 changed 0.0597–0.1436.
- Protected anchors `h1-0`, `header-0`, `nav-0` and sections 0–2: 0.0.
- The tool explicitly reports: “Distinctness is not quality. User decides whether either concept is worthwhile.”

Not verified (`unverified`):

- Whether the user prefers v3f to v3e.
- Whether the external reviewer considers the composition problem resolved.
- Real pointer/keyboard/touch behaviour beyond the `<details>` check; the page has no other interaction.
- Hero and top-photo caption contrast over photography; these were protected and not re-measured.

## 4a. Counterexample: change without relationship evidence

A candidate can pass every mechanical check and still fail this protocol.

Suppose a later pass moves the same food photo from a centered inset to a right-hand rail, or puts 本周 and 记录 side by side. The screenshots show new x/y coordinates, `concept compare` reports a nonzero geometry change, and there is no overflow. None of that proves the design relationship improved. If the photo still reads as an unrelated pause, or the two data modules still read as two separate bands that happen to share a row, the edit has only redistributed modules.

What would count as relationship evidence:

- the photo is now read with the water/after-swim text, and the caption and sequence support that;
- the schedule becomes a supporting index while the result becomes the focal comparison, and the reading order reflects that;
- a reader can answer “what belongs with what” without relying on the old section boundaries.

If those claims cannot be observed, do not describe the change as “better composition.” Describe it as a coordinate or layout change and leave the relationship question open. This is a single-page case, not a rule that two-column layouts or moved images are better or worse.

## 5. User feedback

At the time this example was written, **no `user_confirmed` feedback had been recorded** for v3f. The external review remains an attributed opinion. The next step is a side-by-side v3e/v3f comparison shown to the user; if the user reacts, record their words verbatim, keep the Agent's interpretation in a separate field, and do not promote one reaction into a global rule.

This example is intentionally not a “best practice” checklist. It shows one application of the protocol in [design-method.md](../../skills/aestitch/references/design-method.md): identify the content and composition roles, protect confirmed relationships, change one coherent set of relationships, then measure the changed and neighbouring areas at both viewports and leave the aesthetic verdict to the user.

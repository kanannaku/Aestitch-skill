# Creative design method

## 1. Extract principles, not screenshots

When analyzing reference pages, describe:
- visual hierarchy and focal path;
- relationship of typography, whitespace, and information density;
- motion's function: orientation, feedback, or narrative;
- responsiveness and interaction model;
- which details are original to that brand and must **not** be copied.

Aesthetic keywords alone are not implementable. Convert them into testable, contextual choices. Example: "precise" might mean tight alignment, minimal arbitrary radii and consistent baseline rhythm, but it does not universally imply a dark navy palette.

## 2. Create real alternatives

For substantial designs, explore three distinctly different compositions. Contrast layout grammar, main focal object, typography roles, and interactions, not just color. State tradeoffs. Avoid claiming one is "objectively best." Let the user choose or combine principles explicitly.

## 3. Define design intent before editing

Write a short change contract:
- approved visual traits to retain;
- areas allowed to change;
- the single primary design problem this pass fixes;
- interaction/accessibility/mobile constraints;
- expected evidence (baseline/candidate screenshots and notes).

## 4. Iterate carefully

Only modify relevant UI code. Verify actual browser output. Re-run at mobile and desktop sizes. When pixel changes appear, inspect *why* the page changed. Log failures and explicit user accept/reject decisions.

## 5. Composition-aware iteration

Before modifying or introducing a visual element, identify:

1. **Content role** — why the element exists, what content it carries, and what the reader should do with it.
2. **Compositional role** — how it relates to adjacent sections, the focal hierarchy and the page's sequence.
3. **Visual-system relationship** — how typography, colour, crop, geometry, spacing and rhythm connect it to the rest of the page.
4. **Responsive role** — whether it needs a different composition on smaller screens, and what must remain legible or ordered.
5. **Change impact** — which previously intentional relationships may be disrupted.

Do not automatically forbid centered images, repeated sections, high-contrast type or asymmetric layouts. Ask whether each decision is deliberate, content-appropriate and coherent with the current design intent.

### Relationship evidence

A design intent is only useful if it corresponds to an observable relationship in the rendered page. Separate two kinds of evidence:

- **Coordinate change** — an element moved, grew, shrank or changed columns. This proves the edit executed; it does not prove the composition improved.
- **Relationship change** — the new arrangement changes how content is read, compared or grouped: what belongs with what, what is seen first, what becomes a sequence, what can now be understood without the old container.

For each local edit, state the intended relationship and the rendered observation that would support or falsify it. Example: “the photo now belongs to the water/after-swim column” is a relationship claim; “the photo moved from x=340 to x=973” is only a coordinate change. Measure geometry as evidence, then inspect whether grouping, reading order and emphasis actually changed.

Ask: **does the new composition change how a reader understands the content, or does it only redistribute the same modules?** This is a design-review question for the Agent and user, not a score the CLI can decide.

### Semantic relationships between grouped elements

Spatial proximity is not a content relationship. When elements share a group, column or row, state what the grouping expresses: a common theme, a time order, a contrast, a cause, or a deliberate juxtaposition. The relationship can be carried by composition, explanatory text, sequence, a rule or separation; it does not have to be a label on every adjacent element.

Do not invent a personal event, time or data point to make the layout look justified. If the available content does not support a relationship, separate the elements or explicitly leave the relationship unclaimed.

### Local composition check

After a module is rearranged, inspect both the group and its sub-regions:

- whether text and numbers still read as belonging together;
- whether whitespace is a deliberate pause or an accidental hole left by a grid or flex parameter;
- whether image size, crop and colour relate to their text and to the surrounding page;
- whether the mobile arrangement preserves the content relationship rather than only compressing the desktop layout;
- what is observable and what remains unverified.

Do not automatically remove all whitespace, apply a universal photo filter, or force one font size or weight. These are contextual decisions; record the evidence and let the user judge the result.

### Image integration

An image is part of the composition, not a decorative pause. State what it is evidence of, which text it belongs with, and why its crop, scale and alignment are what they are. A centered inset image is valid when it gives a specific object a quiet pause inside a text sequence; a full-bleed band is valid when the scene itself is the content. The same image can be right in one relationship and wrong in another. Check:

- whether the image is isolated from the content it illustrates;
- whether its scale and crop express a deliberate relationship to the text and neighbouring modules;
- whether it changes the page's rhythm or only fills a gap;
- whether its responsive crop still reads at phone width.

### Rhythm review

A page can repeat a module shape without becoming a template, and can vary every module and still feel random. At page scale, ask:

- What is the dominant visual tempo, and where does it intentionally change?
- Does every section open and close in the same way, regardless of its content function?
- Does the variation carry meaning (data vs. narrative vs. people) or is it decoration?
- After a local edit, does the page still have a beginning, middle and end, or has it become a stack of equal bands?

Do not impose a maximum count of repeated sections or a fixed alternation pattern. Repetition and asymmetry are both valid when they serve the content and the confirmed intent.

### Typography roles

Name each type role by job, not by font name: display, reading, data, caption, interface. For each role, record the rendered size, weight, line-height, measure and contrast at desktop and mobile widths. Readability is measured on the rendered page, not inferred from the stylesheet. WCAG contrast is a baseline for body and functional text (4.5:1 for normal text, 3:1 for large text); it is not an aesthetic target and does not by itself make a typographic system good.

Do not fix one Chinese body size, one maximum number of weights, or one universal scale. A three-role system is a possible outcome, not a required template. The role, reading distance and content density determine the values.

After editing, inspect the changed element, its immediate neighbours and the full-page composition at desktop and mobile sizes. Record observed facts separately from agent interpretations and user-confirmed decisions.

### Rendered readability is an exit condition

Before declaring an implementation ready for handoff, measure text readability on the rendered page at the required viewports and relevant interface states.

For applicable ordinary text, WCAG AA contrast of 4.5:1 is the minimum verification threshold; for qualifying large text, 3:1 applies. These are accessibility requirements, not aesthetic targets.

Classify each finding as PASS, FAIL, or UNKNOWN. Missing measurements, unresolved failures, or incomplete coverage must never be reported as passing.

A design may remain an experimental candidate with known failures, but it must not be described as having passed readability verification.

Do not automatically alter font sizes, palettes, material finishes, or artistic direction merely to satisfy a measurement. Investigate the affected element and apply a scoped correction before rechecking.

## 6. Resist style collapse

Reject automatic use of generic purple/blue gradients, unnecessary glowing orbs, all-card interfaces, meaningless 3D, a single repeated animation, and oversized centered hero layouts **unless** the current product's design concept justifies them. The user may prefer any of these when intentionally chosen; avoid universal prohibitions.

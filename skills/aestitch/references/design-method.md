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

## 5. Resist style collapse

Reject automatic use of generic purple/blue gradients, unnecessary glowing orbs, all-card interfaces, meaningless 3D, a single repeated animation, and oversized centered hero layouts **unless** the current product's design concept justifies them. The user may prefer any of these when intentionally chosen; avoid universal prohibitions.

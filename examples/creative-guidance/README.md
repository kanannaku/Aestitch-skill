# Creative Guidance examples

These JSON files illustrate the v0.4 **protocol draft** in
[`skills/aestitch/references/creative-guidance.md`](../../skills/aestitch/references/creative-guidance.md).

They are working-note examples, not CLI output. Aestitch v0.3.1 does not create or
validate these files automatically; the Agent writes them only after the user confirms
the relevant statements.

- `intent.example.json` — what the site is for and what the user actually said.
- `direction.example.json` — one direction card with thesis, mechanism, trade-off and risk.
- `feedback.example.json` — a verbatim user reaction, kept separate from the Agent's interpretation.

Do not treat an example project, quote or preference as a real user's taste.

`confirmed: true` in `feedback.example.json` is a recorded declaration that the user
gave the feedback. It is not identity verification; the local CLI cannot authenticate
who operated the keyboard.

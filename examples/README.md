# Safe local smoke test

The unit test suite makes temporary synthetic screenshots. It does not access external websites or upload user screenshots. Run `python -m unittest discover -s tests -v`. For a real page, install Playwright Chromium and run the `capture` commands shown in README.

`creative-guidance/` contains minimal intent, direction and feedback JSON examples for the v0.4.0 documentation-only protocol. They are notes the Agent may write after user confirmation, not commands or CLI output.

`design-review/` contains a [worked composition-iteration example](design-review/composition-iteration.example.md) from a single-page experiment. The site and evidence are fictional or test-workspace material; it is not a template or an approved design. It shows how to separate observed evidence, external review and user-confirmed feedback during a local edit.

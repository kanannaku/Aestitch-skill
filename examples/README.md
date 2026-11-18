# Safe local smoke test

The unit test suite makes temporary synthetic screenshots. It does not access external websites or upload user screenshots. Run `python -m unittest discover -s tests -v`. For a real page, install Playwright Chromium and run the `capture` commands shown in README.

`creative-guidance/` contains minimal intent, direction and feedback JSON examples for the v0.4 protocol draft. They are notes the Agent may write after user confirmation, not commands or CLI output.

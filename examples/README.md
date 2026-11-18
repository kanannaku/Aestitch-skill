# Safe local smoke test

The unit test suite makes temporary synthetic screenshots. It does not access external websites or upload user screenshots. Run `python -m unittest discover -s tests -v`. For a real page, install Playwright Chromium and run the `capture` commands shown in README.

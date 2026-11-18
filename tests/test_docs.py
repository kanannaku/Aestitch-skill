"""Documentation stays aligned with the real CLI and the v0.4 protocol draft."""
from pathlib import Path
import argparse
import json
import re
import shlex
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "aestitch" / "scripts"))
from aestitch import make_parser

DOC_FILES = [
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "skills" / "aestitch" / "SKILL.md",
    ROOT / "examples" / "evaluation-protocol.md",
]

FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
# `uv run [--project PATH] aestitch [--root PATH] <subcommand> ...`
CLI_LINE = re.compile(r"^(?:uv run(?: --project \S+)? )?aestitch(?: --root \S+)?(?:\s+(.*))?$")
# Lines that demonstrate a shell session or contain placeholders are not parsed.
SKIP_MARKERS = ("...", "<", ">", "{", "}", "|")
SHELL_PROMPTS = ("$ ", "> ", "PS ", "PS>", "C:\\", "λ ")


def cli_commands() -> set[str]:
    parser = make_parser()
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return set(action.choices)


def executable_examples(path: Path) -> list[str]:
    """Return real CLI command lines from fenced code blocks only."""
    text = path.read_text(encoding="utf-8")
    examples = []
    for block in FENCE.findall(text):
        for raw in block.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith(SHELL_PROMPTS):
                continue
            if any(marker in line for marker in SKIP_MARKERS):
                continue
            if CLI_LINE.match(line):
                examples.append(line)
    return examples


def example_failures(path: Path, parser: argparse.ArgumentParser) -> tuple[int, list[str]]:
    """Validate every executable example in one document; return (checked, failures)."""
    checked = 0
    failures = []
    for line in executable_examples(path):
        checked += 1
        try:
            argv = shlex.split(line)
        except ValueError as exc:
            failures.append(f"{path.name}: unparsable quoting: {line} ({exc})")
            continue
        if argv and argv[0] != "aestitch":
            # `uv run` form: drop tokens until `aestitch`.
            argv = argv[argv.index("aestitch"):] if "aestitch" in argv else argv
        try:
            parser.parse_args(argv[1:])
        except (SystemExit, argparse.ArgumentError, ValueError) as exc:
            failures.append(f"{path.name}: {line} -> {exc}")
    return checked, failures


class DocumentationTest(unittest.TestCase):
    def test_documented_commands_exist(self):
        commands = cli_commands()
        missing = []
        for path in DOC_FILES:
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"\baestitch[ \t]+([a-z][a-z0-9-]*)", text):
                name = match.group(1)
                if name not in commands:
                    missing.append(f"{path.name}: aestitch {name}")
        self.assertEqual(missing, [], "Unknown commands in docs: " + ", ".join(missing))

    def test_documented_cli_examples_parse(self):
        """Every fenced `aestitch ...` example must be a real, parseable command."""
        parser = make_parser()
        parser.exit_on_error = False  # raise ArgumentError instead of exiting
        failures = []
        checked = 0
        for path in DOC_FILES:
            count, found = example_failures(path, parser)
            checked += count
            failures.extend(found)
        self.assertGreater(checked, 0, "No executable CLI examples were found in docs")
        self.assertEqual(failures, [], "Invalid CLI examples:\n" + "\n".join(failures))

    def test_invalid_example_is_detected(self):
        """The parser check must actually catch a wrong flag, not just command names."""
        parser = make_parser()
        parser.exit_on_error = False
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "bad.md"
            doc.write_text("```powershell\naestitch experiment record --id x --bogus-flag\n```\n",
                           encoding="utf-8")
            checked, failures = example_failures(doc, parser)
        self.assertEqual(checked, 1)
        self.assertTrue(failures)

    def test_creative_guidance_examples_are_valid_json(self):
        folder = ROOT / "examples" / "creative-guidance"
        for name in ("intent.example.json", "direction.example.json", "feedback.example.json"):
            data = json.loads((folder / name).read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict)
            self.assertEqual(data["schema_version"], 1)

    def test_protocol_doc_does_not_claim_new_cli(self):
        text = (ROOT / "skills" / "aestitch" / "references" / "creative-guidance.md").read_text(encoding="utf-8")
        self.assertIn("does **not** add new CLI commands", text)
        self.assertIn("triage", text)
        self.assertIn("regression", text)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "skills" / "aestitch" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import aestitch as cli
import aestitch_workflows as w


class TestWorkflows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with redirect_stdout(StringIO()):
            cli.init(self.root)

    def make_refs(self):
        left = w.add_reference(self.root, "Editorial", "https://example.org/editorial", None,
                               "portfolio", "Large scale type", "typography")
        right = w.add_reference(self.root, "Immersive", "https://example.org/immersive", None,
                                "portfolio", "Quiet use of motion", "motion")
        return left, right

    def test_reference_url_not_fetched_and_not_confirmed(self):
        item, _ = self.make_refs()
        self.assertFalse(item["accessed"])
        self.assertEqual(item["observation_status"], "unverified")
        self.assertEqual(len(w.list_references(self.root)), 2)
        with self.assertRaises(ValueError):
            w.add_reference(self.root, "password", "https://me:pass@example.com", None, "", "", "")
        with self.assertRaises(ValueError):
            w.add_reference(self.root, "bad", "javascript:alert(1)", None, "", "", "")

    def test_reference_image_is_copied_privately_and_checked(self):
        file = self.root / "in.png"
        file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"test fixture")
        item = w.add_reference(self.root, "Screenshot", None, str(file), "home", "", "layout")
        copy = self.root / ".aestitch" / item["source"]
        self.assertTrue(copy.exists())
        self.assertEqual(item["sha256"], w.digest(copy))
        self.assertTrue((self.root / ".aestitch/.gitignore").exists())
        bad = self.root / "fake.png"
        bad.write_bytes(b"not a png")
        with self.assertRaises(ValueError):
            w.add_reference(self.root, "Bad", None, str(bad), "", "", "")

    def test_taste_allows_uncertainty_and_context(self):
        left, right = self.make_refs()
        w.taste_compare(self.root, left["id"], right["id"], "both", "I like each for different reasons", "homepage")
        w.taste_compare(self.root, left["id"], right["id"], "unsure", "", "article view")
        report = w.taste_report(self.root)
        self.assertIn("both", report)
        self.assertIn("unsure", report)
        self.assertIn("contextual", report)
        with self.assertRaises(ValueError):
            w.taste_compare(self.root, left["id"], "fake", "left", "", "")

    def test_contract_draft_approval_requires_user_and_local_evidence(self):
        left, _ = self.make_refs()
        created = w.contract_create(self.root, "home", "Show projects", "Editorial asymmetry", "app/home", [left["id"]])
        self.assertEqual(created["status"], "draft")
        with self.assertRaises(ValueError):
            w.contract_create(self.root, "home", "", "", "", [])
        screenshot = self.root / "prototype.png"
        screenshot.write_bytes(b"project screenshot")
        with self.assertRaises(ValueError):
            w.contract_approve(self.root, "home", str(screenshot), "approved", False)
        with self.assertRaises(ValueError):
            w.contract_approve(self.root, "home", str(screenshot), "", True)
        approved = w.contract_approve(self.root, "home", str(screenshot), "I approve this composition", True)
        self.assertEqual(approved["status"], "approved")
        self.assertIn("sha256", approved["visual_evidence"][0])
        self.assertIn("Editorial asymmetry", w.contract_markdown(approved))
        with self.assertRaises(ValueError):
            w.contract_approve(self.root, "home", str(screenshot), "again", True)

    def test_scope_flags_budget_and_dependency_drift(self):
        src = self.root / "src"; src.mkdir()
        (src / "page.tsx").write_text("export default function A() { return null }")
        (self.root / "package.json").write_text(json.dumps({"dependencies": {"react": "18.0.0"}}))
        w.scope_snapshot(self.root, "initial", False)
        with self.assertRaises(ValueError):
            w.scope_snapshot(self.root, "initial", False)
        (src / "page.tsx").write_text("export default function B() { return null }")
        (self.root / "package.json").write_text(json.dumps({"dependencies": {"react": "18.0.0", "gsap": "3.0.0"}}))
        (src / "extra.tsx").write_text("export const X = 1")
        result, status = w.scope_check(self.root, "initial", ["src"], 2, 2, 0, 0)
        self.assertEqual(status, 2)
        self.assertIn("package.json", result["out_of_scope"])
        self.assertIn("dependencies:gsap", result["dependencies_added"])
        self.assertTrue((self.root / ".aestitch/reports/scope-report.md").exists())

    def test_scope_requires_explicit_scope_and_rejects_traversal(self):
        (self.root / "index.html").write_text("<h1>before</h1>")
        w.scope_snapshot(self.root, "baseline", False)
        (self.root / "index.html").write_text("<h1>after</h1>")
        result, status = w.scope_check(self.root, "baseline", [], 2, 2, 0, 0)
        self.assertEqual(status, 2)
        self.assertTrue(any("no approved" in x for x in result["review_reasons"]))
        with self.assertRaises(ValueError):
            w.scope_check(self.root, "baseline", ["../secret"], 2, 2, 0, 0)
        result, status = w.scope_check(self.root, "baseline", ["index.html"], 0, 1, 0, 0)
        self.assertEqual(status, 0)
        self.assertEqual(result["status"], "within_budget")

    def test_scope_excludes_generated_and_ignores_symlinks(self):
        (self.root / "index.html").write_text("x")
        w.scope_snapshot(self.root, "baseline", False)
        (self.root / ".aestitch" / "profile.json").write_text((self.root / ".aestitch" / "profile.json").read_text())
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "evil.tsx").write_text("fake")
        result, status = w.scope_check(self.root, "baseline", ["index.html"], 0, 0, 0, 0)
        self.assertEqual(status, 0)
        self.assertFalse(result["added"])

    def test_end_to_end_cli_commands(self):
        def run(*args):
            out = StringIO()
            with redirect_stdout(out):
                status = cli.main(["--root", str(self.root), *args])
            return status, out.getvalue()
        self.assertEqual(run("reference", "add", "--label", "Demo", "--url", "https://example.org")[0], 0)
        refs = w.list_references(self.root)
        self.assertEqual(run("contract", "create", "--page", "home", "--goal", "Publish", "--direction", "Editorial", "--scope", "app/page.tsx", "--reference", refs[0]["id"])[0], 0)
        self.assertEqual(run("contract", "show", "--page", "home")[0], 0)
        self.assertEqual(run("scope", "snapshot")[0], 0)
        self.assertEqual(run("scope", "check")[0], 0)


if __name__ == "__main__":
    unittest.main()

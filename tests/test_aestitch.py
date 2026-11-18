import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

SCRIPT = Path(__file__).resolve().parents[1] / "skills/aestitch/scripts/aestitch.py"
spec = importlib.util.spec_from_file_location("aestitch_cli", SCRIPT)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class TestAestitch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assertEqual(a.init(self.root), 0)

    def test_init_is_idempotent_and_profile_private(self):
        self.assertEqual(a.init(self.root), 0)
        self.assertTrue((self.root / ".aestitch/.gitignore").exists())
        data = json.loads((self.root / ".aestitch/profile.json").read_text())
        self.assertEqual(data["feedback"], [])

    def test_memory_record_and_brief(self):
        self.assertEqual(a.record(self.root, "avoid", "color", "No purple glow", "homepage"), 0)
        out = self.root / "brief.md"
        self.assertEqual(a.brief(self.root, str(out)), 0)
        brief = out.read_text()
        self.assertIn("No purple glow", brief)
        self.assertIn("homepage", brief)
        d = a.read_json(self.root / ".aestitch/profile.json")
        self.assertEqual(d["feedback"][0]["source"], "user-confirmed")

    def test_reject_remote_capture_by_default(self):
        with self.assertRaisesRegex(ValueError, "Remote capture"):
            a.validate_url("https://example.com", False)
        self.assertEqual(a.validate_url("http://127.0.0.1:3000", False), "http://127.0.0.1:3000")
        with self.assertRaisesRegex(ValueError, "no embedded credentials"):
            a.validate_url("https://foo:bar@example.com", True)
        with self.assertRaises(ValueError):
            a.validate_url("file:///etc/passwd", True)

    def test_html_file_restricted_to_project(self):
        inside = self.root / "index.html"
        inside.write_text("<h1>Test</h1>")
        self.assertEqual(a.validate_html_file(self.root, str(inside)), inside.resolve())
        with self.assertRaisesRegex(ValueError, "inside the target project"):
            a.validate_html_file(self.root, str(SCRIPT.parents[3] / "examples/demo/index.html"))

    def test_guard_missing_evidence_writes_report(self):
        status = a.guard(self.root, 12.0, 24)
        self.assertEqual(status, 2)
        report = a.read_json(self.root / ".aestitch/reports/guard-report.json")
        self.assertTrue(all(x["status"] == "missing_evidence" for x in report["checks"]))

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow not installed")
    def test_visual_diff_reports_changed_pixels(self):
        from PIL import Image
        for viewport in ("desktop", "mobile"):
            bp = self.root / f".aestitch/screenshots/baseline/{viewport}.png"
            cp = self.root / f".aestitch/screenshots/candidate/{viewport}.png"
            bp.parent.mkdir(parents=True, exist_ok=True)
            cp.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (40, 30), "white").save(bp)
            Image.new("RGB", (40, 30), "black" if viewport == "desktop" else "white").save(cp)
        self.assertEqual(a.guard(self.root, 12, 24), 0)
        report = a.read_json(self.root / ".aestitch/reports/guard-report.json")
        self.assertEqual(report["checks"][0]["status"], "needs_review")
        self.assertAlmostEqual(report["checks"][0]["changed_pct"], 100.0)
        self.assertEqual(report["checks"][1]["status"], "change_observed")
        self.assertEqual(report["checks"][1]["changed_pct"], 0.0)
        self.assertTrue((self.root / ".aestitch/reports/diff-desktop.png").exists())

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow not installed")
    def test_hue_shift_is_not_missed_by_luminance_threshold(self):
        from PIL import Image
        before = self.root / "before.png"
        after = self.root / "after.png"
        Image.new("RGB", (20, 20), (37, 43, 36)).save(before)
        Image.new("RGB", (20, 20), (27, 71, 59)).save(after)
        result = a.compare_images(before, after, self.root / "diff.png", 24)
        self.assertEqual(result["changed_pct"], 100.0)

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow not installed")
    def test_dimension_mismatch_requires_review(self):
        from PIL import Image
        for vp in ("desktop", "mobile"):
            bp = self.root / f".aestitch/screenshots/baseline/{vp}.png"
            cp = self.root / f".aestitch/screenshots/candidate/{vp}.png"
            bp.parent.mkdir(parents=True, exist_ok=True)
            cp.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (30, 30), "white").save(bp)
            Image.new("RGB", (30, 35), "white").save(cp)
        self.assertEqual(a.guard(self.root, 12, 24), 2)
        report = a.read_json(self.root / ".aestitch/reports/guard-report.json")
        self.assertTrue(all(x["status"] == "dimension_mismatch" for x in report["checks"]))

    def test_cli_main(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(a.main(["--root", str(self.root), "brief"]), 0)
        self.assertIn("No preferences recorded", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

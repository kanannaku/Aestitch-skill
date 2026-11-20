"""Offline and deterministic coverage for v0.3 creative workflow.

Browser E2E is opt-in (AESTITCH_TEST_CHROMIUM) so normal CI stays portable.
"""
import os
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "aestitch" / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))
from aestitch import init, main
from aestitch_creative import (
    _clear_text_contrast_derived, _fit_observation_id, _geometry_delta, _local_url,
    _next_concept_observation_id, _trusted_html, concept_add, concept_compare, concept_render,
    fidelity_compare, observe, observe_report, record_text_contrast_evidence,
    text_contrast_gate, text_contrast_markdown, text_contrast_status,
)


class CreativeWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        init(self.root)
        self.html_a = self.root / "a.html"
        self.html_b = self.root / "b.html"
        self.html_a.write_text('<!doctype html><html><title>A</title><body><h1>A</h1></body></html>', encoding="utf8")
        self.html_b.write_text('<!doctype html><html><title>B</title><body><h1>B</h1></body></html>', encoding="utf8")

    def test_observe_rejects_untrusted_sources(self):
        with self.assertRaisesRegex(ValueError, "explicit"):
            _local_url("https://example.org/", False)
        with self.assertRaises(ValueError):
            _local_url("file:///etc/passwd", True)
        with self.assertRaises(ValueError):
            _local_url("http://name:password@localhost:3000/", False)
        self.assertEqual(_local_url("http://127.0.0.1:3000", False), "http://127.0.0.1:3000")
        with self.assertRaises(ValueError):
            observe(self.root, "outside", "https://example.org", None, "desktop", 1)
        with self.assertRaises(ValueError):
            observe(self.root, "too-many", None, str(self.html_a), "desktop", 6)
        with self.assertRaises(ValueError):
            _trusted_html(self.root, str(Path(__file__)))

    def test_add_prototypes_no_clobber_no_approval(self):
        a = concept_add(self.root, "a", "Type", "Type is architecture", "Large offset title", str(self.html_a))
        self.assertEqual(a["status"], "unreviewed")
        self.assertEqual(a["scope"], "macro")
        self.assertTrue((self.root / a["prototype"]).exists())
        with self.assertRaisesRegex(ValueError, "exists"):
            concept_add(self.root, "a", "Type", "Type", "Mechanism", str(self.html_b))
        with self.assertRaises(ValueError):
            concept_add(self.root, "bad/slug", "Type", "Type", "Mechanism", str(self.html_b))

    def test_identical_prototypes_flagged(self):
        for cid in ("left", "right"):
            concept_add(self.root, cid, cid, "Same idea", "Same mechanism", str(self.html_a))
        result = concept_compare(self.root, "left", "right", "desktop")
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(result["same_source_hash"])
        self.assertTrue(any("Identical" in warning for warning in result["review_reasons"]))

    def test_geometry_is_not_beauty(self):
        a = {"viewport": {"width": 1440, "height": 900}, "anchors": [{"key": "h1-0", "rect": {"x": 0, "y": 0, "width": 500, "height": 100}}]}
        b = {"viewport": {"width": 1440, "height": 900}, "anchors": [{"key": "h1-0", "rect": {"x": 300, "y": 200, "width": 500, "height": 100}}]}
        d = _geometry_delta(a, b)
        self.assertEqual(d["matched_anchors"], 1)
        self.assertGreater(d["mean_normalized_geometry_change"], 0)
        self.assertNotIn("beauty", d)

    def test_missing_render_requires_evidence(self):
        concept_add(self.root, "spatial", "Spatial", "Space", "Nodes", str(self.html_a))
        concept_add(self.root, "typographic", "Editorial", "Type", "Editorial", str(self.html_b))
        result = concept_compare(self.root, "spatial", "typographic", "desktop")
        self.assertIn("browser-rendered", " ".join(result["review_reasons"]))
        with self.assertRaises(ValueError):
            fidelity_compare(self.root, "spatial", "missing", "desktop")

    def test_cli_help_and_subcommand_parser(self):
        self.assertEqual(main(["--root", str(self.root), "concept", "add", "--id", "draft",
                               "--title", "Draft", "--thesis", "Research", "--mechanism", "Motion",
                               "--html-file", str(self.html_a)]), 0)
        self.assertEqual(main(["--root", str(self.root), "concept", "compare", "--left", "draft",
                               "--right", "draft"]), 2)

    def test_renders_preserve_observation_history(self):
        concept_add(self.root, "a", "A", "One", "Mechanism", str(self.html_a))
        calls = []

        def fake_observe(root, obs_id, *args, **kwargs):
            calls.append((obs_id, kwargs.get("overwrite")))
            return {"id": obs_id}

        with patch("aestitch_creative.observe", side_effect=fake_observe):
            concept_render(self.root, "a", "desktop")
            first = json.loads((self.root / ".aestitch" / "concepts" / "a" / "concept.json").read_text(encoding="utf-8"))
            concept_render(self.root, "a", "desktop")
            second = json.loads((self.root / ".aestitch" / "concepts" / "a" / "concept.json").read_text(encoding="utf-8"))

        self.assertEqual(first["observation_id"], "concept-a")
        self.assertEqual(second["observation_id"], "concept-a-r2")
        self.assertEqual(second["observation_ids"], ["concept-a", "concept-a-r2"])
        self.assertEqual([c[0] for c in calls], ["concept-a", "concept-a-r2"])
        self.assertTrue(all(c[1] is False for c in calls))

    def test_observation_id_fits_slug_limit(self):
        concept_id = "a" * 63
        rec = {"observation_id": "concept-" + concept_id, "observation_ids": []}
        candidate = _next_concept_observation_id(self.root / ".aestitch", concept_id, rec)
        self.assertLessEqual(len(candidate), 63)
        self.assertTrue(candidate.startswith("concept-"))

    def test_report_marks_legacy_observation_context_unknown(self):
        base = self.root / ".aestitch" / "observations" / "legacy"
        base.mkdir(parents=True)
        (base / "manifest.json").write_text(json.dumps({
            "id": "legacy",
            "source": "offline-html",
            "viewports": {"desktop": {
                "evidence": {"title": "Legacy", "documentHeight": 900,
                             "horizontalOverflow": False, "controls": [], "anchors": []},
                "frames": [],
            }},
        }), encoding="utf-8")
        report = observe_report(self.root, "legacy")
        self.assertIn("legacy/unknown", report)
        self.assertIn("Evidence scope: legacy/unknown", report)

    def test_report_surfaces_capture_context(self):
        base = self.root / ".aestitch" / "observations" / "modern"
        base.mkdir(parents=True)
        (base / "manifest.json").write_text(json.dumps({
            "id": "modern",
            "source": "offline-html",
            "capture_context": {"browser": "chromium", "reduced_motion": "reduce",
                                "screenshots": {"animations": "disabled"}},
            "evidence_scope": ["static_layout", "scroll_positions"],
            "viewports": {"desktop": {
                "capture_context": {"viewport": {"width": 1440, "height": 900},
                                    "reduced_motion": "reduce", "animations": "disabled"},
                "evidence_scope": ["static_layout", "scroll_positions"],
                "evidence": {"title": "Modern", "documentHeight": 900,
                             "horizontalOverflow": False, "controls": [], "anchors": []},
                "frames": [],
            }},
        }), encoding="utf-8")
        report = observe_report(self.root, "modern")
        self.assertIn("viewport=1440x900", report)
        self.assertIn("reduced_motion=reduce", report)
        self.assertIn("animations=disabled", report)
        self.assertIn("static_layout", report)

    def test_concurrent_render_is_rejected_without_overwrite(self):
        concept_add(self.root, "race", "Race", "One", "Mechanism", str(self.html_a))
        started = threading.Event()
        release = threading.Event()

        def slow_observe(root, obs_id, *args, **kwargs):
            started.set()
            release.wait(10)
            return {"id": obs_id}

        errors = []

        def first_render():
            try:
                with patch("aestitch_creative.observe", side_effect=slow_observe):
                    concept_render(self.root, "race", "desktop")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        thread = threading.Thread(target=first_render)
        thread.start()
        try:
            self.assertTrue(started.wait(5), "first render did not start")
            # Age alone must never authorise takeover of an active render.
            old = time.time() - 3 * 60 * 60
            os.utime(self.root / ".aestitch" / "concepts" / "race" / ".render.lock",
                     (old, old))
            with self.assertRaisesRegex(ValueError, "already being rendered"):
                concept_render(self.root, "race", "desktop")
        finally:
            release.set()
            thread.join(10)
        self.assertEqual(errors, [])
        rec = json.loads((self.root / ".aestitch" / "concepts" / "race" / "concept.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rec["observation_id"], "concept-race")
        self.assertFalse((self.root / ".aestitch" / "concepts" / "race" / ".render.lock").exists())

    def test_dead_owner_lock_is_recovered(self):
        concept_add(self.root, "recover", "Recover", "One", "Mechanism", str(self.html_a))
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        lock = self.root / ".aestitch" / "concepts" / "recover" / ".render.lock"
        lock.write_text(json.dumps({"pid": dead.pid, "token": "dead-token",
                                    "started": time.time() - 3600}), encoding="utf-8")
        with patch("aestitch_creative.observe", return_value={"id": "concept-recover"}):
            concept_render(self.root, "recover", "desktop")
        rec = json.loads((self.root / ".aestitch" / "concepts" / "recover" / "concept.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(rec["observation_id"], "concept-recover")
        self.assertFalse(lock.exists())

    def test_lock_release_never_deletes_a_foreign_lock(self):
        concept_add(self.root, "owner", "Owner", "One", "Mechanism", str(self.html_a))
        started = threading.Event()
        release = threading.Event()

        def slow_observe(root, obs_id, *args, **kwargs):
            started.set()
            release.wait(10)
            return {"id": obs_id}

        def first_render():
            with patch("aestitch_creative.observe", side_effect=slow_observe):
                concept_render(self.root, "owner", "desktop")

        thread = threading.Thread(target=first_render)
        thread.start()
        lock = self.root / ".aestitch" / "concepts" / "owner" / ".render.lock"
        try:
            self.assertTrue(started.wait(5))
            lock.write_text(json.dumps({"pid": os.getpid(), "token": "foreign",
                                        "started": time.time()}), encoding="utf-8")
        finally:
            release.set()
            thread.join(10)
        self.assertTrue(lock.exists(), "release deleted a lock owned by another token")
        self.assertEqual(json.loads(lock.read_text(encoding="utf-8"))["token"], "foreign")
        lock.unlink()

    def test_malformed_lock_requires_manual_recovery(self):
        concept_add(self.root, "unknown", "Unknown", "One", "Mechanism", str(self.html_a))
        lock = self.root / ".aestitch" / "concepts" / "unknown" / ".render.lock"
        lock.write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "delete this file manually"):
            concept_render(self.root, "unknown", "desktop")
        self.assertTrue(lock.exists())

    def test_active_lock_is_respected_across_processes(self):
        concept_add(self.root, "proc", "Proc", "One", "Mechanism", str(self.html_a))
        concept_dir = self.root / ".aestitch" / "concepts" / "proc"
        code = (
            "import sys, time\n"
            f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
            "from pathlib import Path\n"
            "from aestitch_creative import _concept_write_lock\n"
            f"with _concept_write_lock(Path({str(concept_dir)!r})):\n"
            "    print('LOCKED', flush=True)\n"
            "    time.sleep(20)\n"
        )
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE,
                                text=True)
        self.addCleanup(lambda: (proc.kill(), proc.wait()))
        try:
            line: list[str] = []
            reader = threading.Thread(target=lambda: line.append(proc.stdout.readline()),
                                      daemon=True)
            reader.start()
            reader.join(10)
            self.assertTrue(line, "child process did not acquire the lock in time")
            self.assertEqual(line[0].strip(), "LOCKED")
            with self.assertRaisesRegex(ValueError, "already being rendered"):
                concept_render(self.root, "proc", "desktop")
        finally:
            proc.kill()
            proc.wait()

    def test_failed_render_is_traceable_and_never_reused(self):
        concept_add(self.root, "failure", "Failure", "One", "Mechanism", str(self.html_a))

        class BrokenPlaywright:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def __getattr__(self, name):
                raise RuntimeError("browser failed mid-capture")

        fake_module = types.ModuleType("playwright.sync_api")
        fake_module.sync_playwright = lambda: BrokenPlaywright()
        with patch.dict(sys.modules, {"playwright.sync_api": fake_module}):
            with self.assertRaises(RuntimeError):
                concept_render(self.root, "failure", "desktop")

        concept = json.loads((self.root / ".aestitch" / "concepts" / "failure" / "concept.json")
                             .read_text(encoding="utf-8"))
        self.assertIsNone(concept["observation_id"])
        failed = json.loads((self.root / ".aestitch" / "observations" / "concept-failure" /
                             "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(failed["status"], "failed")
        self.assertIn("browser failed", failed["error"])
        self.assertFalse((self.root / ".aestitch" / "concepts" / "failure" / ".render.lock").exists())

        with patch("aestitch_creative.observe", return_value={"id": "concept-failure-r2"}) as mocked:
            concept_render(self.root, "failure", "desktop")
        self.assertEqual(mocked.call_args[0][1], "concept-failure-r2")
        concept = json.loads((self.root / ".aestitch" / "concepts" / "failure" / "concept.json")
                             .read_text(encoding="utf-8"))
        self.assertEqual(concept["observation_id"], "concept-failure-r2")

    def test_orphan_observation_directory_owns_its_id(self):
        state = self.root / ".aestitch"
        (state / "observations" / "concept-orphan").mkdir(parents=True)
        candidate = _next_concept_observation_id(state, "orphan",
                                                 {"observation_ids": [], "observation_id": None})
        self.assertEqual(candidate, "concept-orphan-r2")
        with self.assertRaisesRegex(ValueError, "Observation exists"):
            observe(self.root, "concept-orphan", None, str(self.html_a), "desktop", 1)

    def test_existing_observation_wins_over_missing_browser_dependency(self):
        state = self.root / ".aestitch"
        (state / "observations" / "concept-orphan").mkdir(parents=True)
        with patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            with self.assertRaisesRegex(ValueError, "Observation exists"):
                observe(self.root, "concept-orphan", None, str(self.html_a), "desktop", 1)

    def test_missing_browser_dependency_fails_before_creating_observation(self):
        obs_dir = self.root / ".aestitch" / "observations" / "fresh-obs"
        with patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            with self.assertRaisesRegex(ValueError, "Install Playwright"):
                observe(self.root, "fresh-obs", None, str(self.html_a), "desktop", 1, claim=True)
        self.assertFalse(obs_dir.exists())

    def test_long_concept_ids_do_not_collide(self):
        base_a = "concept-" + "a" * 63
        base_b = "concept-" + "a" * 62 + "b"
        first = _fit_observation_id(base_a, "-r2")
        second = _fit_observation_id(base_b, "-r2")
        self.assertLessEqual(len(first), 63)
        self.assertLessEqual(len(second), 63)
        self.assertNotEqual(first, second)


class TextContrastGateTest(unittest.TestCase):
    """Deterministic gate logic. Browser measurement is exercised separately."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        init(self.root)

    @staticmethod
    def manifest(*statuses, observation_status="completed", requested=None):
        names = ("desktop", "mobile")
        viewports = {names[i]: {"text_contrast": {"status": status, "counts": {}, "rows": []}}
                     for i, status in enumerate(statuses)}
        return {"id": "sample", "status": observation_status,
                "requested_viewports": list(requested) if requested is not None else list(viewports),
                "viewports": viewports}

    def write_observation(self, obs_id, manifest):
        base = self.root / ".aestitch" / "observations" / obs_id
        base.mkdir(parents=True)
        (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def finish_observation(self, obs_id, manifest):
        """Create the evidence files and persist the manifest that names them."""
        base = self.root / ".aestitch" / "observations" / obs_id
        base.mkdir(parents=True)
        manifest["id"] = obs_id
        record_text_contrast_evidence(self.root, obs_id, manifest)
        (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_only_full_pass_is_pass(self):
        self.assertEqual(text_contrast_status(self.manifest("PASS", "PASS")), "PASS")
        self.assertEqual(text_contrast_status(self.manifest("PASS", "FAIL")), "FAIL")
        self.assertEqual(text_contrast_status(self.manifest("PASS", "UNKNOWN")), "UNKNOWN")
        self.assertEqual(text_contrast_status(self.manifest("PASS", "NOT_RUN")), "UNKNOWN")
        self.assertEqual(text_contrast_status(self.manifest("NOT_RUN")), "NOT_RUN")
        self.assertEqual(text_contrast_status({"viewports": {}}), "NOT_RUN")

    def test_failed_or_unfinished_observation_never_passes(self):
        self.assertEqual(text_contrast_status(self.manifest("PASS", observation_status="failed")), "UNKNOWN")
        self.assertEqual(text_contrast_status(self.manifest("PASS", "PASS", observation_status="in_progress")), "UNKNOWN")
        self.assertEqual(text_contrast_status(self.manifest("FAIL", observation_status="failed")), "FAIL")
        self.assertEqual(text_contrast_status({"viewports": {"desktop": {"text_contrast": {"status": "PASS"}}}}), "UNKNOWN")

    def test_missing_expected_viewport_blocks_aggregate(self):
        manifest = self.manifest("PASS", requested=("desktop", "mobile"))
        self.assertEqual(text_contrast_status(manifest), "UNKNOWN")
        obs_id = self._persist("partial", manifest)
        gate_status, detail = text_contrast_gate(self.root, obs_id)
        self.assertEqual(gate_status, "UNKNOWN")
        self.assertIn("mobile", detail)
        self.assertEqual(main(["--root", str(self.root), "observe", "report", "--id", "partial",
                               "--require-text-contrast-pass"]), 2)

    def _persist(self, obs_id, manifest):
        manifest["id"] = obs_id
        self.write_observation(obs_id, manifest)
        return obs_id

    def test_one_low_contrast_functional_label_blocks_the_gate(self):
        manifest = {"viewports": {"desktop": {"text_contrast": {
            "status": "FAIL",
            "counts": {"measured": 40, "pass": 39, "fail": 1, "unknown": 0},
            "rows": [{"selector": ".archive-count", "tag": "span", "text": "02 条",
                      "font_size_px": 10, "font_weight": 400, "large_text": False,
                      "ratio": 2.38, "threshold": 4.5, "status": "FAIL", "reason": ""}],
        }}}}
        self.assertEqual(text_contrast_status(manifest), "FAIL")
        payload = {"observation": "sample", "overall_status": "FAIL",
                   "scope": "initial static page load", "large_text_rule": "rule",
                   "viewports": {"desktop": manifest["viewports"]["desktop"]["text_contrast"]}}
        markdown = text_contrast_markdown(payload)
        self.assertIn("2.38:1", markdown)
        self.assertIn(".archive-count", markdown)
        self.assertIn("must not be reported as a passing readability check", markdown)

    def test_gate_requires_observation_to_exist(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            text_contrast_gate(self.root, "missing")

    def test_legacy_observation_gate_is_not_run(self):
        base = self.root / ".aestitch" / "observations" / "legacy"
        base.mkdir(parents=True)
        (base / "manifest.json").write_text(json.dumps({
            "id": "legacy", "source": "offline-html",
            "viewports": {"desktop": {"evidence": {}, "frames": []}},
        }), encoding="utf-8")
        status, detail = text_contrast_gate(self.root, "legacy")
        self.assertEqual(status, "NOT_RUN")
        self.assertIn("cannot be reported as passing", detail)

    def test_failed_manifest_with_desktop_pass_blocks_cli(self):
        manifest = self.manifest("PASS", observation_status="failed", requested=("desktop",))
        obs_id = self._persist("failed-pass", manifest)
        status, detail = text_contrast_gate(self.root, obs_id)
        self.assertEqual(status, "UNKNOWN")
        self.assertIn("not completed", detail)
        self.assertEqual(main(["--root", str(self.root), "observe", "report",
                               "--id", "failed-pass", "--require-text-contrast-pass"]), 2)

    def test_single_requested_desktop_pass_exits_zero(self):
        manifest = self.manifest("PASS", requested=("desktop",))
        self.finish_observation("desktop-only", manifest)
        self.assertEqual(text_contrast_gate(self.root, "desktop-only")[0], "PASS")
        self.assertEqual(main(["--root", str(self.root), "observe", "report",
                               "--id", "desktop-only", "--require-text-contrast-pass"]), 0)

    def test_both_viewports_pass_exits_zero(self):
        manifest = self.manifest("PASS", "PASS", requested=("desktop", "mobile"))
        self.finish_observation("both-pass", manifest)
        self.assertEqual(text_contrast_gate(self.root, "both-pass")[0], "PASS")
        self.assertEqual(main(["--root", str(self.root), "observe", "report",
                               "--id", "both-pass", "--require-text-contrast-pass"]), 0)

    def test_fail_and_unknown_block_gate(self):
        for index, status in enumerate(("FAIL", "UNKNOWN")):
            obs_id = f"blocked-{index}"
            self._persist(obs_id, self.manifest(status, requested=("desktop",)))
            self.assertEqual(text_contrast_gate(self.root, obs_id)[0], status)
            self.assertEqual(main(["--root", str(self.root), "observe", "report",
                                   "--id", obs_id, "--require-text-contrast-pass"]), 2)

    def test_missing_or_foreign_evidence_blocks_pass(self):
        manifest = self.manifest("PASS", requested=("desktop",))
        self.finish_observation("missing-file", manifest)
        (self.root / manifest["text_contrast"]["evidence"]).unlink()
        status, detail = text_contrast_gate(self.root, "missing-file")
        self.assertEqual(status, "UNKNOWN")
        self.assertIn("missing", detail)

        foreign = self.manifest("PASS", requested=("desktop",))
        self.finish_observation("foreign-evidence", foreign)
        evidence = self.root / foreign["text_contrast"]["evidence"]
        payload = json.loads(evidence.read_text(encoding="utf-8"))
        payload["observation"] = "another-observation"
        evidence.write_text(json.dumps(payload), encoding="utf-8")
        status, detail = text_contrast_gate(self.root, "foreign-evidence")
        self.assertEqual(status, "UNKNOWN")
        self.assertIn("different observation", detail)

    def test_corrupt_evidence_record_blocks_without_crashing(self):
        manifest = self.manifest("PASS", requested=("desktop",))
        self.finish_observation("corrupt", manifest)
        path = self.root / ".aestitch" / "observations" / "corrupt" / "manifest.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["text_contrast"]["viewports"] = ["not-a-mapping"]
        path.write_text(json.dumps(saved), encoding="utf-8")
        status, detail = text_contrast_gate(self.root, "corrupt")
        self.assertEqual(status, "UNKNOWN")
        self.assertIn("no per-viewport", detail)

    def test_overwrite_cleanup_removes_only_known_derived_files(self):
        base = self.root / ".aestitch" / "observations" / "cleanup"
        base.mkdir(parents=True)
        for name in ("text-contrast.json", "text-contrast.json.tmp", "text-contrast.md",
                     "manifest.json", "notes.txt"):
            (base / name).write_text("{}", encoding="utf-8")
        removed = _clear_text_contrast_derived(base)
        self.assertEqual(sorted(removed), ["text-contrast.json", "text-contrast.json.tmp",
                                           "text-contrast.md"])
        self.assertTrue((base / "manifest.json").is_file())
        self.assertTrue((base / "notes.txt").is_file())

    def test_cli_flags_parse(self):
        from aestitch import make_parser
        parser = make_parser()
        capture = parser.parse_args(["observe", "capture", "--id", "x", "--html-file", "a.html",
                                     "--check-text-contrast"])
        self.assertTrue(capture.check_text_contrast)
        report = parser.parse_args(["observe", "report", "--id", "x", "--require-text-contrast-pass"])
        self.assertTrue(report.require_text_contrast_pass)
        default = parser.parse_args(["observe", "capture", "--id", "x", "--html-file", "a.html"])
        self.assertFalse(default.check_text_contrast)


@unittest.skipUnless(os.environ.get("AESTITCH_TEST_CHROMIUM"), "Optional Chromium E2E")
class BrowserIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        init(self.root)
        self.html_a = self.root / "a.html"
        self.html_b = self.root / "b.html"
        self.html_a.write_text('<!doctype html><html><title>A</title><body><h1>A</h1></body></html>', encoding="utf8")
        self.html_b.write_text('<!doctype html><html><title>B</title><body><h1>B</h1></body></html>', encoding="utf8")

    def test_browser_capture_concept_and_fidelity(self):
        from aestitch_workflows import add_reference, list_references
        from aestitch_creative import observe_report
        ref = add_reference(self.root, "Local", "http://localhost:3000/", None, "", "", "")
        item = observe(self.root, "sample", None, str(self.html_a), "desktop", 2,
                       reference=ref["id"])
        self.assertEqual(len(item["viewports"]["desktop"]["frames"]), 2)
        self.assertIn("Observation: sample", observe_report(self.root, "sample"))
        self.assertTrue((self.root / item["viewports"]["desktop"]["frames"][0]["path"]).is_file())
        self.assertFalse(list_references(self.root)[0]["accessed"])  # offline does not visit URL
        concept_add(self.root, "a", "A", "One", "A mechanism", str(self.html_a))
        concept_add(self.root, "b", "B", "Other", "Other mechanism", str(self.html_b))
        concept_render(self.root, "a", "desktop")
        concept_render(self.root, "b", "desktop")
        comp = concept_compare(self.root, "a", "b", "desktop")
        self.assertTrue(comp["composition_evidence"])
        diff = fidelity_compare(self.root, "a", "concept-b", "desktop")
        self.assertEqual(diff["pixels"]["status"], "compared")

    def test_observation_context_and_render_history(self):
        concept_add(self.root, "a", "A", "One", "A mechanism", str(self.html_a))
        concept_render(self.root, "a", "desktop")
        first = json.loads((self.root / ".aestitch" / "concepts" / "a" / "concept.json").read_text(encoding="utf-8"))
        first_id = first["observation_id"]
        first_manifest = json.loads((self.root / ".aestitch" / "observations" / first_id / "manifest.json").read_text(encoding="utf-8"))
        desktop = first_manifest["viewports"]["desktop"]
        self.assertEqual(desktop["capture_context"]["viewport"], {"width": 1440, "height": 900})
        self.assertEqual(desktop["capture_context"]["reduced_motion"], "reduce")
        self.assertEqual(desktop["capture_context"]["animations"], "disabled")
        self.assertIn("static_layout", desktop["evidence_scope"])
        self.assertIn("interaction", first_manifest["not_observed"])

        concept_render(self.root, "a", "desktop")
        second = json.loads((self.root / ".aestitch" / "concepts" / "a" / "concept.json").read_text(encoding="utf-8"))
        self.assertNotEqual(second["observation_id"], first_id)
        self.assertIn(first_id, second["observation_ids"])
        self.assertTrue((self.root / ".aestitch" / "observations" / first_id / "manifest.json").is_file())

    def test_demo_interactions_and_mobile_overflow(self):
        from playwright.sync_api import sync_playwright
        base = Path(__file__).resolve().parents[1] / "examples" / "creative-lab"
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,
                executable_path=os.environ.get('AESTITCH_CHROMIUM_EXECUTABLE') or None)
            try:
                for filename, locator, changed in (
                    ('computational-space.html', '#toggle', '#state'),
                    ('editorial-object.html', '#sample', '#bars i:first-child'),
                ):
                    context = browser.new_context(viewport={'width':390,'height':844},
                                                  reduced_motion='reduce')
                    try:
                        page=context.new_page()
                        context.route('**/*',lambda route: route.abort())
                        page.set_content((base/filename).read_text(encoding='utf8'))
                        self.assertFalse(page.evaluate('document.documentElement.scrollWidth > innerWidth + 2'))
                        initial=page.locator(changed).evaluate('(el) => el.textContent + ":" + getComputedStyle(el).height')
                        page.locator(locator).click()
                        after=page.locator(changed).evaluate('(el) => el.textContent + ":" + getComputedStyle(el).height')
                        self.assertNotEqual(initial,after)
                    finally:
                        context.close()
            finally:
                browser.close()

    def test_live_localhost_observation(self):
        from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
        from threading import Thread
        from aestitch_creative import observe
        class LocalHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                body=b'<!doctype html><html><head><title>Local demo</title></head><body><h1>Local evidence</h1><button>Explore</button></body></html>'
                self.send_response(200)
                self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server=ThreadingHTTPServer(('127.0.0.1',0),LocalHandler)
        self.addCleanup(server.server_close)
        thread=Thread(target=server.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        url=f'http://127.0.0.1:{server.server_port}/'
        try:
            manifest=observe(self.root,'local-demo',url,None,'desktop',1)
        except Exception as exc:
            # Some hosted sandbox environments disallow even loopback in Chromium.
            if 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc):
                self.skipTest('Chromium loopback network access prohibited by environment')
            raise
        page=manifest['viewports']['desktop']
        self.assertEqual(page['http_status'],200)
        self.assertEqual(page['evidence']['title'],'Local demo')
        self.assertTrue(any(a['key']=='h1-0' for a in page['evidence']['anchors']))

    CONTRAST_FIXTURE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Contrast fixture</title>
<style>
  body { background: #fff; font-family: sans-serif; }
  #pass-normal { color: #000; font-size: 16px; }
  #fail-low { color: #808080; font-size: 16px; }
  #pass-large { color: #8a8a8a; font-size: 24px; font-weight: 400; }
  #transparent-parent { background: rgba(255,255,255,0.5); }
  #transparent-parent p { color: #000; font-size: 16px; }
  #unknown-gradient { color: #000; background: linear-gradient(#fff, #000); }
  #hidden { display: none; color: #eee; }
  #low-button { color: #777; background: #222; font-size: 14px; }
  #low-input-submit, #low-input-reset, #low-input-button {
    color: #777; background: #222; font-size: 14px;
  }
  #hidden-input { display: none; }
  #default-label-input { color: #000; background: #000; font-size: 14px; }
  .gradient-parent { background: linear-gradient(#fff, #000); }
  .gradient-parent > #opaque-child { background: #111; color: #eee; font-size: 16px; padding: 4px; }
  .gradient-parent > #transparent-child { color: #000; font-size: 16px; }
  .blend-parent { mix-blend-mode: multiply; }
  .blend-parent > #blended-opaque-child { background: #111; color: #eee; font-size: 16px; padding: 4px; }
  .opacity-parent { opacity: 0.5; }
  .opacity-parent > #opacity-opaque-child { background: #111; color: #eee; font-size: 16px; padding: 4px; }
  .filter-parent { filter: invert(1); }
  .filter-parent > #filter-opaque-child { background: #111; color: #eee; font-size: 16px; padding: 4px; }
</style></head>
<body>
<p id="pass-normal">Readable normal text</p>
<p id="fail-low">Low contrast normal text</p>
<p id="pass-large">Large heading text</p>
<div id="transparent-parent"><p>Text on translucent parent</p></div>
<p id="unknown-gradient">Text over gradient</p>
<p id="hidden">Hidden text</p>
<button id="low-button">Archive entry</button>
<input type="submit" id="low-input-submit" value="Submit low">
<input type="reset" id="low-input-reset" value="Reset low">
<input type="button" id="low-input-button" value="Button low">
<input type="submit" id="hidden-input" value="Hidden submit">
<input type="submit" id="default-label-input">
<div class="gradient-parent"><div id="opaque-child">Opaque child text</div></div>
<div class="gradient-parent"><p id="transparent-child">Transparent child text</p></div>
<div class="gradient-parent blend-parent"><div id="blended-opaque-child">Blended opaque text</div></div>
<div class="gradient-parent opacity-parent"><div id="opacity-opaque-child">Opacity opaque text</div></div>
<div class="gradient-parent filter-parent"><div id="filter-opaque-child">Filter opaque text</div></div>
</body></html>
"""

    @staticmethod
    def row_for(text_contrast, needle):
        for row in text_contrast.get("rows", []):
            if needle in row.get("selector", "") or needle in row.get("text", ""):
                return row
        return None

    def test_text_contrast_fixture_passes_fails_and_unknowns(self):
        fixture = self.root / "contrast.html"
        fixture.write_text(self.CONTRAST_FIXTURE, encoding="utf-8")
        observation = observe(self.root, "contrast", None, str(fixture), "desktop", 1,
                              check_text_contrast=True)
        item = observation["viewports"]["desktop"]["text_contrast"]
        self.assertEqual(item["status"], "FAIL")
        self.assertEqual(item["thresholds"]["normal"], 4.5)
        self.assertIn("interaction_states", item["scope"]["not_covered"])

        self.assertEqual(self.row_for(item, "pass-normal")["status"], "PASS")
        low = self.row_for(item, "fail-low")
        self.assertEqual(low["status"], "FAIL")
        self.assertLess(low["ratio"], 4.5)
        large = self.row_for(item, "pass-large")
        self.assertEqual(large["status"], "PASS")
        self.assertEqual(large["threshold"], 3.0)
        self.assertTrue(large["large_text"])
        self.assertEqual(self.row_for(item, "translucent")["status"], "PASS")
        gradient = self.row_for(item, "unknown-gradient")
        self.assertEqual(gradient["status"], "UNKNOWN")
        self.assertTrue(gradient["background_complex"])
        self.assertIsNone(self.row_for(item, "Hidden text"))
        self.assertEqual(self.row_for(item, "Archive entry")["status"], "FAIL")
        # Native input buttons expose their visible label through value, not a text node.
        for needle in ("Submit low", "Reset low", "Button low"):
            row = self.row_for(item, needle)
            self.assertIsNotNone(row, needle)
            self.assertEqual(row["status"], "FAIL", needle)
        self.assertAlmostEqual(self.row_for(item, "Submit low")["ratio"],
                               self.row_for(item, "Archive entry")["ratio"], places=2)
        # A missing value still renders a localized default label and must be measured.
        default_label = self.row_for(item, "default-label-input")
        self.assertIsNotNone(default_label)
        self.assertEqual(default_label["status"], "FAIL")
        self.assertEqual(default_label["text"], "(browser default label)")
        self.assertIsNone(self.row_for(item, "Hidden submit"))
        # Coverage boundary: an opaque child panel hides the gradient ancestor.
        self.assertEqual(self.row_for(item, "Opaque child text")["status"], "PASS")
        # Transparent child still depends on the gradient: unknown.
        self.assertEqual(self.row_for(item, "Transparent child text")["status"], "UNKNOWN")
        # Group effects above the opaque panel can still change final colours.
        self.assertEqual(self.row_for(item, "Blended opaque text")["status"], "UNKNOWN")
        self.assertEqual(self.row_for(item, "Opacity opaque text")["status"], "UNKNOWN")
        self.assertEqual(self.row_for(item, "Filter opaque text")["status"], "UNKNOWN")

        evidence = self.root / ".aestitch" / "observations" / "contrast" / "text-contrast.json"
        self.assertTrue(evidence.is_file())
        self.assertTrue(evidence.with_suffix(".md").is_file())
        self.assertEqual(json.loads(evidence.read_text(encoding="utf-8"))["overall_status"], "FAIL")
        self.assertIn("Text contrast: FAIL", observe_report(self.root, "contrast"))
        self.assertEqual(main(["--root", str(self.root), "observe", "report", "--id", "contrast",
                               "--require-text-contrast-pass"]), 2)
        self.assertEqual(main(["--root", str(self.root), "observe", "capture",
                               "--id", "contrast-cli", "--html-file", str(fixture),
                               "--viewport", "desktop", "--steps", "1",
                               "--check-text-contrast"]), 2)

    def test_overwrite_clears_stale_text_contrast_evidence(self):
        fixture = self.root / "contrast.html"
        fixture.write_text(self.CONTRAST_FIXTURE, encoding="utf-8")
        observe(self.root, "stale", None, str(fixture), "desktop", 1, check_text_contrast=True)
        base = self.root / ".aestitch" / "observations" / "stale"
        self.assertTrue((base / "text-contrast.json").is_file())
        self.assertTrue((base / "text-contrast.md").is_file())
        manifest = observe(self.root, "stale", None, str(fixture), "desktop", 1, overwrite=True)
        self.assertNotIn("text_contrast", manifest)
        self.assertFalse((base / "text-contrast.json").exists())
        self.assertFalse((base / "text-contrast.md").exists())
        self.assertEqual(text_contrast_gate(self.root, "stale")[0], "NOT_RUN")
        self.assertEqual(main(["--root", str(self.root), "observe", "report", "--id", "stale",
                               "--require-text-contrast-pass"]), 2)

    def test_text_contrast_default_off_and_cli_exit_codes(self):
        plain = observe(self.root, "plain", None, str(self.html_a), "desktop", 1)
        self.assertNotIn("text_contrast", plain["viewports"]["desktop"])
        self.assertEqual(main(["--root", str(self.root), "observe", "report", "--id", "plain"]), 0)
        self.assertEqual(main(["--root", str(self.root), "observe", "report", "--id", "plain",
                               "--require-text-contrast-pass"]), 2)
        self.assertEqual(main(["--root", str(self.root), "observe", "capture", "--id", "pass-cli",
                               "--html-file", str(self.html_a), "--viewport", "desktop",
                               "--steps", "1", "--check-text-contrast"]), 0)
        passed = json.loads((self.root / ".aestitch" / "observations" / "pass-cli" /
                             "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(passed["requested_viewports"], ["desktop"])
        self.assertEqual(passed["text_contrast"]["overall_status"], "PASS")


class DesignGuardianRegressionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        init(self.root)

    def test_appended_page_content_still_compares_first_viewport(self):
        from PIL import Image
        from aestitch import compare_top_viewport
        a, b, d = self.root / 'a.png', self.root / 'b.png', self.root / 'diff.png'
        Image.new('RGB',(100,200),'white').save(a)
        Image.new('RGB',(100,300),'white').save(b)
        result = compare_top_viewport(a,b,d,10,100,150)
        self.assertEqual(result['status'],'compared')
        self.assertEqual(result['changed_pct'],0)
        self.assertEqual(result['compared_region']['height'],150)
        self.assertTrue(d.exists())

    def test_relative_preference_without_approval(self):
        from aestitch_workflows import add_reference, taste_compare, taste_report
        a=add_reference(self.root,'A','https://example.com',None,'','','')
        b=add_reference(self.root,'B','https://example.org',None,'','','')
        result=taste_compare(self.root,a['id'],b['id'],'neither',
                    'Both insufficient, B feels more refined','homepage','right','neither')
        self.assertEqual(result['relative_preference'],'right')
        self.assertEqual(result['absolute_acceptance'],'neither')
        report=taste_report(self.root)
        self.assertIn('Relative preference: right',report)
        self.assertIn('Absolute acceptance: neither',report)

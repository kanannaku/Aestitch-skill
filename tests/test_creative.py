"""Offline and deterministic coverage for v0.3 creative workflow.

Browser E2E is opt-in (AESTITCH_TEST_CHROMIUM) so normal CI stays portable.
"""
import os
from pathlib import Path
import json
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "aestitch" / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))
from aestitch import init, main
from aestitch_creative import (
    _fit_observation_id, _geometry_delta, _local_url, _next_concept_observation_id,
    _trusted_html, concept_add, concept_compare, concept_render, fidelity_compare,
    observe, observe_report,
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

    def test_long_concept_ids_do_not_collide(self):
        base_a = "concept-" + "a" * 63
        base_b = "concept-" + "a" * 62 + "b"
        first = _fit_observation_id(base_a, "-r2")
        second = _fit_observation_id(base_b, "-r2")
        self.assertLessEqual(len(first), 63)
        self.assertLessEqual(len(second), 63)
        self.assertNotEqual(first, second)


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

"""Offline and deterministic coverage for v0.3 creative workflow.

Browser E2E is opt-in (AESTITCH_TEST_CHROMIUM) so normal CI stays portable.
"""
import os
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "aestitch" / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))
from aestitch import init, main
from aestitch_creative import (
    _geometry_delta, _local_url, _trusted_html, concept_add, concept_compare,
    concept_render, fidelity_compare, observe, observe_report,
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

"""Evidence-first creative workflow for Aestitch.

Observe trusted rendered pages, register independently authored prototypes, compare
composition evidence, and check a design-to-code handoff. No AI judgement is
performed here: geometry/pixel differences are observations, never beauty scores.
"""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import shutil
from typing import Any
from urllib.parse import urlsplit

from aestitch_workflows import digest, list_references, load, save, slug, state_dir

VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}
MAX_STEPS = 5
MAX_HTML_BYTES = 2 * 1024 * 1024


def _local_url(url: str, allow_remote: bool) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only http(s) URLs without embedded credentials are supported")
    hostname = parsed.hostname.lower()
    try:
        local = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        local = hostname == "localhost"
    if not local and not allow_remote:
        raise ValueError("Remote observation needs explicit --allow-remote; use only trusted URLs")
    if len(url) > 2048:
        raise ValueError("URL exceeds limit")
    return url


def _trusted_html(root: Path, html_file: str) -> Path:
    project = root.expanduser().resolve()
    source = Path(html_file).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() not in (".html", ".htm"):
        raise ValueError("A self-contained .html file is required")
    if not source.is_relative_to(project):
        raise ValueError("HTML must be inside the target project")
    if source.stat().st_size > MAX_HTML_BYTES:
        raise ValueError("HTML exceeds 2MB; use a smaller standalone prototype")
    return source


# Only geometry, visible headings and exposed CSS facts; never form values/cookies.
_PAGE_EVIDENCE_SCRIPT = r"""() => {
  const clamp = (x,n=160) => String(x || '').trim().replace(/\s+/g,' ').slice(0,n);
  const rect = (e) => {
    const r=e.getBoundingClientRect();
    return {x:Math.round(r.left),y:Math.round(r.top),width:Math.round(r.width),height:Math.round(r.height)};
  };
  const style = (e) => {
    const s=getComputedStyle(e);
    return {fontFamily:s.fontFamily,fontSize:s.fontSize,fontWeight:s.fontWeight,
      lineHeight:s.lineHeight,color:s.color,background:s.backgroundColor,display:s.display};
  };
  const selectors=['header','nav','main','h1','h2','figure','section','footer'];
  const anchors=[];
  for (const sel of selectors) {
    const nodes=Array.from(document.querySelectorAll(sel)).slice(0,sel==='section'?8:sel==='h2'?8:3);
    nodes.forEach((e,i)=>{
      const b=rect(e);
      if(b.width>0 && b.height>0) anchors.push({key:`${sel}-${i}`,tag:sel,rect:b,style:style(e),text:clamp(e.innerText,110)});
    });
  }
  for (const e of Array.from(document.querySelectorAll('[data-aestitch-anchor]')).slice(0,20)) {
    const key=clamp(e.getAttribute('data-aestitch-anchor'),50);
    if(key) anchors.push({key:`custom:${key}`,tag:e.tagName.toLowerCase(),rect:rect(e),style:style(e),text:clamp(e.innerText,110)});
  }
  const controls=Array.from(document.querySelectorAll('button,a[href],input,select,[role="button"]'))
    .filter(e=>{const r=e.getBoundingClientRect();return r.width>0 && r.height>0;})
    .slice(0,28).map(e=>({tag:e.tagName.toLowerCase(),role:e.getAttribute('role')||'',
      label:clamp(e.getAttribute('aria-label')||e.innerText||e.getAttribute('title'),90),rect:rect(e)}));
  return {title:document.title,url:location.href,viewport:{width:innerWidth,height:innerHeight},
    documentHeight:document.documentElement.scrollHeight,
    horizontalOverflow:document.documentElement.scrollWidth>innerWidth+2,
    missingAlt:document.querySelectorAll('img:not([alt])').length,
    anchors,controls};
}"""


def _capture_one(page: Any, dest: Path, steps: int) -> dict[str, Any]:
    page.evaluate("() => document.fonts.ready")
    page.evaluate("() => window.scrollTo(0,0)")
    evidence = page.evaluate(_PAGE_EVIDENCE_SCRIPT)
    available_scroll = max(0, evidence["documentHeight"] - evidence["viewport"]["height"])
    shots = []
    for step in range(steps):
        position = round(available_scroll * step / max(steps - 1, 1))
        page.evaluate("y => window.scrollTo(0,y)", position)
        page.wait_for_timeout(120)
        shot_path = dest / f"frame-{step:02}.png"
        shot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shot_path), full_page=False, animations="disabled")
        shots.append({"scroll_y": position, "path": str(shot_path)})
    return {"evidence": evidence, "frames": shots}


def observe(root: Path, obs_id: str, url: str | None, html_file: str | None,
            viewport: str, steps: int, allow_remote: bool = False, reference: str = "",
            overwrite: bool = False) -> dict[str, Any]:
    """Capture browser-rendered evidence. URLs are never fetched without this command."""
    state = state_dir(root)
    obs_id = slug(obs_id)
    if (url is None) == (html_file is None):
        raise ValueError("Choose exactly one of --url or --html-file")
    if viewport not in (*VIEWPORTS, "both") or not 1 <= steps <= MAX_STEPS:
        raise ValueError("Invalid viewport or steps (1..5)")
    if url:
        _local_url(url, allow_remote)
    if html_file:
        html_path = _trusted_html(root, html_file)
    if reference:
        refs = {r["id"]: r for r in list_references(root)}
        if reference not in refs:
            raise ValueError("Unknown reference ID")
        ref = refs[reference]
        if url and ref["source_type"] == "url":
            if urlsplit(url).hostname != urlsplit(ref["source"]).hostname:
                raise ValueError("Observed URL host does not match the linked reference")
    base = state / "observations" / obs_id
    manifest_path = base / "manifest.json"
    if manifest_path.exists() and not overwrite:
        raise ValueError("Observation exists; use a new --id or explicit --overwrite")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Install Playwright and Chromium first (aestitch doctor)") from exc
    manifest: dict[str, Any] = {"schema_version": 1, "id": obs_id,
                               "source": "offline-html" if html_file else url,
                               "reference_id": reference or None,
                               "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "capture_type": "offline" if html_file else ("remote" if allow_remote else "local"),
                               "viewports": {}, "interpretation_status": "unreviewed",
                               "note": "DOM/style geometry and screenshots are observations, not design conclusions."}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,
             executable_path=os.environ.get("AESTITCH_CHROMIUM_EXECUTABLE") or None)
        try:
            for vp in VIEWPORTS if viewport == "both" else (viewport,):
                w, h = VIEWPORTS[vp]
                ctx = browser.new_context(viewport={"width": w, "height": h},
                                          device_scale_factor=1, reduced_motion="reduce")
                try:
                    page = ctx.new_page()
                    errors: list[str] = []
                    page.on("pageerror", lambda err: errors.append(str(err)[:200]))
                    if html_file:
                        # Fully offline, no remote URLs, images or CSS may be fetched.
                        ctx.route("**/*", lambda route: route.abort())
                        page.set_content(html_path.read_text(encoding="utf-8"),
                                         wait_until="domcontentloaded", timeout=20000)
                    else:
                        # Restrict requests to the intended host. In particular,
                        # remote pages must not use this tool to reach private
                        # localhost services or third-party tracking resources.
                        intended_host = urlsplit(url).hostname
                        def same_host_only(route: Any) -> None:
                            requested = urlsplit(route.request.url)
                            if requested.scheme in ("http", "https") and requested.hostname == intended_host:
                                route.continue_()
                            else:
                                route.abort()
                        ctx.route("**/*", same_host_only)
                        response = page.goto(url, wait_until="domcontentloaded", timeout=25000)
                        if urlsplit(page.url).hostname != intended_host:
                            raise ValueError("Redirect outside the observed host; supply the final trusted URL")
                    page.wait_for_timeout(200)
                    item = _capture_one(page, base / vp, steps)
                    item["page_errors"] = errors[:12]
                    item["http_status"] = response.status if not html_file and response else None
                    # paths stay relative to target project to make handoff portable
                    for frame in item["frames"]:
                        frame["path"] = Path(frame["path"]).relative_to(root.resolve()).as_posix()
                    manifest["viewports"][vp] = item
                finally:
                    ctx.close()
        finally:
            browser.close()
    save(manifest_path, manifest)
    if reference:
        from aestitch_workflows import _ref_db
        db = load(_ref_db(state), [])
        for item in db:
            if item.get("id") == reference:
                refs = item.setdefault("observation_ids", [])
                if obs_id not in refs:
                    refs.append(obs_id)
                # A linked offline HTML must not imply the reference URL was visited.
                if url and item.get("source_type") == "url":
                    item["accessed"] = True
                item["observation_status"] = "captured_unreviewed"
        save(_ref_db(state), db)
    return manifest


def observe_report(root: Path, obs_id: str) -> str:
    manifest = load(state_dir(root) / "observations" / slug(obs_id) / "manifest.json", None)
    if not isinstance(manifest, dict):
        raise ValueError("Observation not found")
    lines = [f"# Observation: {manifest['id']}", "", f"Source: `{manifest['source']}`", "",
             "Facts below are captured from a rendered browser page. No aesthetic conclusion is inferred.", ""]
    for vp, v in manifest["viewports"].items():
        ev = v["evidence"]
        lines.extend([f"## {vp}", "", f"- Title: {ev['title']}",
                      f"- Document height: {ev['documentHeight']}",
                      f"- Horizontal overflow: {ev['horizontalOverflow']}",
                      f"- Visible controls: {len(ev['controls'])}",
                      f"- Frames: {', '.join(f['path'] for f in v['frames'])}", "",
                      "### Observable anchor geometry and CSS", ""])
        for a in ev["anchors"][:24]:
            lines.append(f"- `{a['key']}`: {a['rect']}; font={a['style']['fontFamily']}; size={a['style']['fontSize']}")
        lines.append("")
    lines += ["## Agent interpretation worksheet", "", "- [ ] Which observable detail is distinctive, and in which frame/anchor?",
              "- [ ] What purpose does it serve? Mark this as hypothesis until a user confirms.",
              "- [ ] What can transfer as a general principle without copying the source's unique assets?",
              "- [ ] Which desired motion/hover/click states are unobserved and require manual interaction or recording?", ""]
    return "\n".join(lines)


def _concept_path(state: Path, concept_id: str) -> Path:
    return state / "concepts" / slug(concept_id)


def concept_add(root: Path, concept_id: str, title: str, thesis: str, mechanism: str,
                html_file: str, mode: str = "macro") -> dict[str, Any]:
    state = state_dir(root)
    if mode not in ("macro", "meso", "micro"):
        raise ValueError("Mode must be macro, meso or micro")
    if not all(x.strip() for x in (title, thesis, mechanism)):
        raise ValueError("Title, thesis and interaction/visual mechanism must be nonempty")
    source = _trusted_html(root, html_file)
    dest = _concept_path(state, concept_id)
    if dest.exists():
        raise ValueError("Concept ID exists; do not overwrite a prior visual experiment")
    dest.mkdir(parents=True)
    target = dest / "prototype.html"
    shutil.copyfile(source, target)
    record: dict[str, Any] = {"schema_version": 1, "id": concept_id, "title": title,
         "thesis": thesis, "mechanism": mechanism, "scope": mode, "status": "unreviewed",
         "prototype": target.relative_to(root.resolve()).as_posix(),
         "sha256": digest(target), "observation_id": None,
         "note": "Agent-authored prototype, not a user-approved design."}
    save(dest / "concept.json", record)
    return record


def concept_load(root: Path, concept_id: str) -> dict[str, Any]:
    item = load(_concept_path(state_dir(root), concept_id) / "concept.json", None)
    if not isinstance(item, dict):
        raise ValueError("Concept does not exist")
    return item


def concept_render(root: Path, concept_id: str, viewport: str) -> dict[str, Any]:
    rec = concept_load(root, concept_id)
    obs_id = f"concept-{slug(concept_id)}"
    obs = observe(root, obs_id, None, str(root.resolve() / rec["prototype"]), viewport, 1,
                  overwrite=True)
    rec["observation_id"] = obs_id
    save(_concept_path(state_dir(root), concept_id) / "concept.json", rec)
    return obs


def _anchor_map(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {a["key"]: a for a in evidence.get("anchors", [])}


def _geometry_delta(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    aa, bb = _anchor_map(a), _anchor_map(b)
    common = sorted(set(aa) & set(bb))
    dx = []
    w = max(a.get("viewport", {}).get("width", 1), 1)
    h = max(a.get("viewport", {}).get("height", 1), 1)
    for key in common:
        ar, br = aa[key]["rect"], bb[key]["rect"]
        delta = sum(abs(ar[k] - br[k]) / (w if k in ("x", "width") else h)
                    for k in ("x", "y", "width", "height")) / 4
        dx.append({"anchor": key, "normalized_change": round(delta, 4)})
    return {"matched_anchors": len(common), "changes": dx,
            "mean_normalized_geometry_change": round(sum(p["normalized_change"] for p in dx) / len(dx), 4) if dx else None}


def concept_compare(root: Path, left: str, right: str, viewport: str) -> dict[str, Any]:
    if left == right or viewport not in VIEWPORTS:
        raise ValueError("Use two different concepts and desktop/mobile viewport")
    a, b = concept_load(root, left), concept_load(root, right)
    warnings = []
    if a["sha256"] == b["sha256"]:
        warnings.append("Identical prototype files: not independent visual exploration")
    if a["thesis"].casefold() == b["thesis"].casefold() or a["mechanism"].casefold() == b["mechanism"].casefold():
        warnings.append("Concept thesis or mechanism repeats; check whether directions truly diverge")
    if not a["observation_id"] or not b["observation_id"]:
        warnings.append("Both concepts must be browser-rendered before composition review")
        geometry = None
    else:
        state = state_dir(root)
        ao = load(state / "observations" / a["observation_id"] / "manifest.json", {})
        bo = load(state / "observations" / b["observation_id"] / "manifest.json", {})
        if viewport not in ao.get("viewports", {}) or viewport not in bo.get("viewports", {}):
            warnings.append("Requested viewport has not been captured for both concepts")
            geometry = None
        else:
            geometry = _geometry_delta(ao["viewports"][viewport]["evidence"], bo["viewports"][viewport]["evidence"])
            if geometry["mean_normalized_geometry_change"] is not None and geometry["mean_normalized_geometry_change"] < 0.025:
                warnings.append("Matched landmarks barely moved; visual directions may share the same composition")
    report = {"schema_version": 1, "left": left, "right": right, "viewport": viewport,
              "same_source_hash": a["sha256"] == b["sha256"],
              "theses": [a["thesis"], b["thesis"]], "mechanisms": [a["mechanism"], b["mechanism"]],
              "composition_evidence": geometry, "review_reasons": warnings,
              "status": "needs_review" if warnings else "evidence_ready",
              "caveat": "Distinctness is not quality. User decides whether either concept is worthwhile."}
    report_dir = state_dir(root) / "reports"
    save(report_dir / f"concept-{left}-vs-{right}-{viewport}.json", report)
    return report


def fidelity_compare(root: Path, concept_id: str, observation_id: str, viewport: str,
                     pixel_threshold: int = 24) -> dict[str, Any]:
    if viewport not in VIEWPORTS or not 0 <= pixel_threshold <= 255:
        raise ValueError("Invalid viewport or pixel threshold")
    state = state_dir(root)
    concept = concept_load(root, concept_id)
    if not concept.get("observation_id"):
        raise ValueError("Render the concept before fidelity checking")
    ref = load(state / "observations" / concept["observation_id"] / "manifest.json", None)
    target = load(state / "observations" / slug(observation_id) / "manifest.json", None)
    if not isinstance(ref, dict) or not isinstance(target, dict):
        raise ValueError("Missing browser evidence")
    if viewport not in ref["viewports"] or viewport not in target["viewports"]:
        raise ValueError("Both observations need the same viewport")
    baseline, candidate = ref["viewports"][viewport], target["viewports"][viewport]
    geom = _geometry_delta(baseline["evidence"], candidate["evidence"])
    from aestitch import compare_images
    screenshot_a = root.resolve() / baseline["frames"][0]["path"]
    screenshot_b = root.resolve() / candidate["frames"][0]["path"]
    report_dir = state / "reports"
    image_result = compare_images(screenshot_a, screenshot_b,
                report_dir / f"fidelity-{concept_id}-{observation_id}-{viewport}.png", pixel_threshold)
    result = {"schema_version": 1, "concept": concept_id, "implementation": observation_id,
              "viewport": viewport, "geometry": geom, "pixels": image_result,
              "observed_issues": {"horizontal_overflow": candidate["evidence"].get("horizontalOverflow"),
                                  "missing_alt": candidate["evidence"].get("missingAlt"),
                                  "page_errors": candidate.get("page_errors", [])},
              "caveat": "Comparisons reveal discrepancies, not aesthetic quality or approval. Inspect the screenshots and interactive states."}
    save(report_dir / f"fidelity-{concept_id}-{observation_id}-{viewport}.json", result)
    return result

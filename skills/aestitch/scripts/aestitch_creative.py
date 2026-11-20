"""Evidence-first creative workflow for Aestitch.

Observe trusted rendered pages, register independently authored prototypes, compare
composition evidence, and check a design-to-code handoff. No AI judgement is
performed here: geometry/pixel differences are observations, never beauty scores.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha1
import ipaddress
import json
import os
from pathlib import Path
import shutil
import time
from typing import Any, Iterator
from urllib.parse import urlsplit
from uuid import uuid4

from aestitch_workflows import digest, list_references, load, save, slug, state_dir

VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}
MAX_STEPS = 5
MAX_HTML_BYTES = 2 * 1024 * 1024
STATIC_EVIDENCE_SCOPE = ["static_layout", "scroll_positions"]
NOT_OBSERVED_STATES = ["interaction", "motion", "hover", "focus", "keyboard"]
# A lock is only reclaimed when its recorded owner process is confirmed dead.
# Age alone never authorises takeover: a legitimate capture may run for hours.
LOCK_RETRY_ATTEMPTS = 5


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness check without new dependencies.

    On Windows `os.kill(pid, 0)` would terminate the process, so use
    OpenProcess/GetExitCodeProcess instead.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    pid, token = data.get("pid"), data.get("token")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    if not isinstance(token, str) or not token:
        return None
    return data


@contextmanager
def _concept_write_lock(concept_dir: Path) -> Iterator[None]:
    """Cross-process single-writer lock for one Concept directory.

    Atomic exclusive create, never time-based preemption: an active render is
    respected regardless of duration. A lock is reclaimed only when its recorded
    owner process is confirmed dead; malformed/unknown ownership is refused with
    an explicit manual-recovery instruction. Release only removes our own lock.
    """
    lock_path = concept_dir / ".render.lock"
    token = uuid4().hex
    payload = json.dumps({"pid": os.getpid(), "token": token, "started": time.time()})
    fd = None
    for _ in range(LOCK_RETRY_ATTEMPTS):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            owner = _read_lock(lock_path)
            if owner is None:
                raise ValueError(
                    "Concept render lock has unknown ownership: " + str(lock_path) +
                    ". If no render is running, delete this file manually and retry.")
            if _pid_alive(owner["pid"]):
                raise ValueError("Concept is already being rendered by another process: " +
                                 str(lock_path) + "; retry after it finishes")
            # Owner process is gone. Re-read to avoid removing a lock that changed
            # between the liveness check and the unlink.
            if _read_lock(lock_path) != owner:
                continue
            try:
                os.unlink(lock_path)
            except OSError:
                pass
            continue
        else:
            break
    if fd is None:
        raise ValueError("Could not acquire the concept render lock; another process holds it")
    try:
        os.write(fd, payload.encode("utf-8"))
        yield
    finally:
        try:
            os.close(fd)
        finally:
            # Only remove the lock if it is still ours; a reclaimed lock belongs
            # to another process and must not be deleted here.
            try:
                if (_read_lock(lock_path) or {}).get("token") == token:
                    lock_path.unlink()
            except OSError:
                pass


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


TEXT_CONTRAST_THRESHOLDS = {"normal": 4.5, "large": 3.0}
TEXT_CONTRAST_NOT_COVERED = [
    "interaction_states", "hover", "focus", "disabled", "pseudo_element_text",
    "pseudo_element_backgrounds", "svg_text", "canvas_or_webgl_text",
    "text_inside_iframes", "images_containing_text", "shadow_dom_text",
    "other_form_controls",
]

# Conservative rendered-text contrast probe. A background is resolved only when the
# ancestor chain paints solid colours with no image, gradient, filter, blend mode or
# opacity composite. Everything else is reported UNKNOWN, never guessed as PASS.
_TEXT_CONTRAST_SCRIPT = r"""() => {
  const MAX_PASS_ROWS = 300;
  const counts = {measured: 0, pass: 0, fail: 0, unknown: 0,
                  skipped_not_rendered: 0, skipped_visually_hidden: 0,
                  svg_text_not_covered: 0};
  const rows = [];
  let passRowsTruncated = false;

  const parseColor = (value) => {
    const text = String(value || '').trim();
    const m = /^rgba?\(\s*([0-9.]+)[,\s]+([0-9.]+)[,\s]+([0-9.]+)(?:[,\s/]+([0-9.]+))?\s*\)$/i.exec(text);
    if (!m) return null;
    const rgb = [Number(m[1]), Number(m[2]), Number(m[3])];
    if (rgb.some((n) => !Number.isFinite(n))) return null;
    const a = m[4] === undefined ? 1 : Number(m[4]);
    if (!Number.isFinite(a)) return null;
    return {r: rgb[0], g: rgb[1], b: rgb[2], a: Math.max(0, Math.min(1, a))};
  };
  const composite = (fg, bg) => {
    const a = fg.a + bg.a * (1 - fg.a);
    if (a <= 0) return {r: 0, g: 0, b: 0, a: 0};
    return {r: (fg.r * fg.a + bg.r * bg.a * (1 - fg.a)) / a,
            g: (fg.g * fg.a + bg.g * bg.a * (1 - fg.a)) / a,
            b: (fg.b * fg.a + bg.b * bg.a * (1 - fg.a)) / a, a};
  };
  const channel = (v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const luminance = (c) => 0.2126 * channel(c.r) + 0.7152 * channel(c.g) + 0.0722 * channel(c.b);
  const contrast = (a, b) => { const x = luminance(a), y = luminance(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const css = (c) => `rgba(${Math.round(c.r)}, ${Math.round(c.g)}, ${Math.round(c.b)}, ${Math.round(c.a * 1000) / 1000})`;
  const pathOf = (el) => {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.id) part += '#' + node.id;
      else if (node.classList && node.classList.length) part += '.' + Array.from(node.classList).slice(0, 2).join('.');
      if (node.parentElement) {
        let index = 1;
        for (let sib = node.previousElementSibling; sib; sib = sib.previousElementSibling) {
          if (sib.tagName === node.tagName) index += 1;
        }
        part += `:nth-of-type(${index})`;
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };
  const directText = (el) => {
    let text = '';
    for (const child of el.childNodes) if (child.nodeType === 3) text += ' ' + child.nodeValue;
    return text.replace(/\s+/g, ' ').trim();
  };
  const resolveBackground = (el, style) => {
    const layers = [];
    let node = el;
    let current = style;
    while (node && node.nodeType === 1) {
      if (current.backgroundImage && current.backgroundImage !== 'none') {
        return {unknown: 'background-image/gradient on ' + pathOf(node)};
      }
      if (current.filter && current.filter !== 'none') return {unknown: 'CSS filter on ' + pathOf(node)};
      if (current.backdropFilter && current.backdropFilter !== 'none') return {unknown: 'backdrop-filter on ' + pathOf(node)};
      if (current.mixBlendMode && current.mixBlendMode !== 'normal') return {unknown: 'mix-blend-mode on ' + pathOf(node)};
      const opacity = parseFloat(current.opacity);
      if (Number.isFinite(opacity) && opacity < 1) return {unknown: 'opacity composite on ' + pathOf(node)};
      if (current.backgroundClip === 'text') return {unknown: 'background-clip:text on ' + pathOf(node)};
      const color = parseColor(current.backgroundColor);
      if (color === null) return {unknown: 'unparsable background-color on ' + pathOf(node)};
      if (color.a > 0) layers.push({color, from: pathOf(node)});
      if (color.a >= 1) {
        // An opaque layer hides ancestor backgrounds, but group effects above it
        // still composite the whole subtree and can change the final colours.
        let above = node.parentElement;
        while (above && above.nodeType === 1) {
          const outer = getComputedStyle(above);
          const outerOpacity = parseFloat(outer.opacity);
          if (Number.isFinite(outerOpacity) && outerOpacity < 1) {
            return {unknown: 'opacity composite above opaque background on ' + pathOf(above)};
          }
          if (outer.filter && outer.filter !== 'none') {
            return {unknown: 'CSS filter above opaque background on ' + pathOf(above)};
          }
          if (outer.mixBlendMode && outer.mixBlendMode !== 'normal') {
            return {unknown: 'mix-blend-mode above opaque background on ' + pathOf(above)};
          }
          above = above.parentElement;
        }
        return {layers};
      }
      node = node.parentElement;
      if (node) current = getComputedStyle(node);
    }
    // Chromium paints an unpainted canvas white.
    layers.push({color: {r: 255, g: 255, b: 255, a: 1}, from: 'canvas-default'});
    return {layers, canvas_default: true};
  };
  const visible = (el, style) => {
    if (style.display === 'none' || style.visibility !== 'visible') return false;
    if (parseFloat(style.opacity) === 0) return false;
    if (style.clip && style.clip !== 'auto') return false;
    if (style.clipPath && style.clipPath !== 'none') return false;
    if (parseFloat(style.textIndent) <= -999) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };

  for (const el of Array.from(document.querySelectorAll('svg text'))) {
    if ((el.textContent || '').trim()) counts.svg_text_not_covered += 1;
  }
  const record = (el, text, style) => {
    const fill = style.webkitTextFillColor && style.webkitTextFillColor !== 'currentcolor'
      ? style.webkitTextFillColor : style.color;
    const color = parseColor(fill);
    const background = resolveBackground(el, style);
    const size = parseFloat(style.fontSize);
    const weight = Number.parseInt(style.fontWeight, 10) || 400;
    const large = size >= 23.99 || (size >= 18.66 && weight >= 700);
    const threshold = large ? 3.0 : 4.5;
    let status = 'UNKNOWN';
    let reason = '';
    let ratio = null;
    let backgroundCss = null;
    if (color === null || !Number.isFinite(size)) {
      reason = 'unparsable text colour or font size';
    } else if (color.a <= 0) {
      counts.skipped_visually_hidden += 1;
      return;
    } else if (background.unknown) {
      reason = background.unknown;
    } else {
      let base = background.layers[background.layers.length - 1].color;
      for (let i = background.layers.length - 2; i >= 0; i -= 1) {
        base = composite(background.layers[i].color, base);
      }
      const textColor = color.a < 1 ? composite(color, base) : color;
      ratio = contrast(textColor, base);
      backgroundCss = css(base);
      status = ratio >= threshold - 0.005 ? 'PASS' : 'FAIL';
    }
    counts.measured += 1;
    if (status === 'PASS') counts.pass += 1;
    else if (status === 'FAIL') counts.fail += 1;
    else counts.unknown += 1;
    const row = {
      selector: pathOf(el), tag: el.tagName.toLowerCase(), text: text.slice(0, 80),
      role: el.getAttribute('role') || '', aria_hidden: el.getAttribute('aria-hidden') === 'true',
      font_size_px: Math.round(size * 100) / 100, font_weight: weight, large_text: large,
      color: color ? css(color) : String(fill), background: backgroundCss,
      background_sources: background.layers ? background.layers.map((layer) => layer.from) : [],
      background_complex: !!background.unknown,
      ratio: ratio === null ? null : Math.round(ratio * 100) / 100,
      threshold, status, reason,
    };
    if (status !== 'PASS') rows.push(row);
    else if (rows.length < MAX_PASS_ROWS) rows.push(row);
    else passRowsTruncated = true;
  };
  const elements = document.body ? [document.body, ...Array.from(document.body.querySelectorAll('*'))] : [];
  for (const el of elements) {
    if (el.closest('svg')) continue;
    if (['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'TITLE', 'META', 'LINK',
         'IFRAME', 'OBJECT', 'EMBED', 'CANVAS'].includes(el.tagName)) continue;
    const text = directText(el);
    if (!text) continue;
    const style = getComputedStyle(el);
    if (!visible(el, style)) { counts.skipped_not_rendered += 1; continue; }
    record(el, text, style);
  }
  // Native input buttons render their value (or a localized default label) as the
  // visible control text; it has no DOM text node, so collect it explicitly.
  const INPUT_BUTTON_TYPES = ['submit', 'reset', 'button'];
  for (const el of Array.from(document.querySelectorAll('input'))) {
    const type = String(el.type || '').toLowerCase();
    if (!INPUT_BUTTON_TYPES.includes(type)) continue;
    const style = getComputedStyle(el);
    if (!visible(el, style)) { counts.skipped_not_rendered += 1; continue; }
    let text = '';
    if (el.hasAttribute('value')) {
      text = String(el.value || '').replace(/\s+/g, ' ').trim();
      // An explicitly empty value renders no label.
      if (!text) continue;
    } else if (type === 'button') {
      // input[type=button] without a value renders no label.
      continue;
    } else {
      text = '(browser default label)';
    }
    record(el, text, style);
  }
  return {
    status: counts.fail > 0 ? 'FAIL' : (counts.unknown > 0 || counts.measured === 0 ? 'UNKNOWN' : 'PASS'),
    thresholds: {normal: 4.5, large: 3.0,
                 large_text_rule: 'font-size >= 24px, or >= 18.66px with weight >= 700'},
    scope: {state: 'initial static page load', scroll_position: 0,
            measured: 'direct text nodes of rendered elements and value text of native submit/reset/button inputs',
            not_covered: ['interaction_states', 'hover', 'focus', 'disabled',
                          'pseudo_element_text', 'pseudo_element_backgrounds', 'svg_text',
                          'canvas_or_webgl_text', 'text_inside_iframes',
                          'images_containing_text', 'shadow_dom_text',
                          'other_form_controls']},
    counts, rows, truncated_pass_rows: passRowsTruncated,
    note: 'Contrast is computed only when the background resolves to solid colours. Complex backgrounds are UNKNOWN, never PASS.',
  };
}"""


def _capture_one(page: Any, dest: Path, steps: int, check_text_contrast: bool = False) -> dict[str, Any]:
    page.evaluate("() => document.fonts.ready")
    page.evaluate("() => window.scrollTo(0,0)")
    evidence = page.evaluate(_PAGE_EVIDENCE_SCRIPT)
    text_contrast = page.evaluate(_TEXT_CONTRAST_SCRIPT) if check_text_contrast else None
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
    item: dict[str, Any] = {"evidence": evidence, "frames": shots}
    if text_contrast is not None:
        item["text_contrast"] = text_contrast
    return item


def _clear_text_contrast_derived(base: Path) -> list[str]:
    """Remove only the known text-contrast artifacts of one observation.

    Rewriting an observation must not leave an older PASS file that the new
    manifest no longer references but a reader could mistake for current evidence.
    """
    removed = []
    for name in ("text-contrast.json", "text-contrast.json.tmp", "text-contrast.md"):
        path = base / name
        try:
            if path.is_file():
                path.unlink()
                removed.append(name)
        except OSError:
            pass
    return removed


def observe(root: Path, obs_id: str, url: str | None, html_file: str | None,
            viewport: str, steps: int, allow_remote: bool = False, reference: str = "",
            overwrite: bool = False, claim: bool = False,
            check_text_contrast: bool = False) -> dict[str, Any]:
    """Capture browser-rendered evidence. URLs are never fetched without this command.

    With claim=True the observation directory is reserved atomically before capture;
    a concurrent reservation fails instead of writing into the same evidence folder.
    """
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
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Install Playwright and Chromium first (aestitch doctor)") from exc
    if claim and not overwrite:
        try:
            base.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise ObservationReserved("Observation ID is already reserved or used: " + obs_id) from exc
    elif base.exists() and not overwrite:
        # An orphan directory from a failed render still owns this ID.
        raise ValueError("Observation exists; use a new --id or explicit --overwrite")
    if overwrite and base.exists():
        # Old derived reports must never survive a rewrite as current evidence.
        _clear_text_contrast_derived(base)
    manifest: dict[str, Any] = {"schema_version": 1, "id": obs_id,
                               "status": "in_progress",
                               "source": "offline-html" if html_file else url,
                               "reference_id": reference or None,
                               "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "capture_type": "offline" if html_file else ("remote" if allow_remote else "local"),
                               "requested_viewports": list(VIEWPORTS) if viewport == "both" else [viewport],
                               "capture_context": {
                                   "browser": "chromium",
                                   "headless": True,
                                   "reduced_motion": "reduce",
                                   "screenshots": {"animations": "disabled"},
                                   "device_scale_factor": 1,
                               },
                               "evidence_scope": list(STATIC_EVIDENCE_SCOPE),
                               "not_observed": list(NOT_OBSERVED_STATES),
                               "viewports": {}, "interpretation_status": "unreviewed",
                               "note": "DOM/style geometry and screenshots are observations, not design conclusions."}
    if claim:
        # Durable in-progress marker: a crash leaves a traceable, non-reusable ID.
        save(manifest_path, manifest)
    try:
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
                        item = _capture_one(page, base / vp, steps, check_text_contrast)
                        item["capture_context"] = {
                            "viewport": {"width": w, "height": h},
                            "reduced_motion": "reduce",
                            "animations": "disabled",
                            "device_scale_factor": 1,
                            "steps": steps,
                            "capture_type": manifest["capture_type"],
                        }
                        item["evidence_scope"] = list(STATIC_EVIDENCE_SCOPE)
                        if check_text_contrast:
                            item["evidence_scope"].append("text_contrast")
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
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["failed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        manifest["error"] = str(exc)[:500]
        save(manifest_path, manifest)
        raise
    manifest["status"] = "completed"
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if check_text_contrast:
        record_text_contrast_evidence(root, obs_id, manifest)
        if "text_contrast" not in manifest["evidence_scope"]:
            manifest["evidence_scope"].append("text_contrast")
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


def _expected_text_contrast_viewports(manifest: dict[str, Any]) -> list[str]:
    """Viewports this observation promised to capture, falling back to those recorded.

    `requested_viewports` is written by current captures. Legacy manifests without it
    are judged on the viewports they actually contain.
    """
    requested = manifest.get("requested_viewports")
    if isinstance(requested, list):
        ordered = [vp for vp in requested if isinstance(vp, str) and vp in VIEWPORTS]
        if ordered:
            return ordered
    viewports = manifest.get("viewports")
    return [vp for vp in viewports] if isinstance(viewports, dict) else []


def text_contrast_status(manifest: dict[str, Any]) -> str:
    """Aggregate rendered text-contrast status without ever upgrading missing data to PASS."""
    viewports = manifest.get("viewports")
    if not isinstance(viewports, dict):
        return "NOT_RUN"
    statuses = []
    for vp in _expected_text_contrast_viewports(manifest):
        item = viewports.get(vp)
        payload = item.get("text_contrast") if isinstance(item, dict) else None
        statuses.append(payload.get("status", "UNKNOWN") if isinstance(payload, dict) else "NOT_RUN")
    if not statuses or all(status == "NOT_RUN" for status in statuses):
        return "NOT_RUN"
    if "FAIL" in statuses:
        return "FAIL"
    if manifest.get("status") != "completed":
        # A failed or unfinished capture never becomes a completed measurement.
        return "UNKNOWN"
    if any(status in ("UNKNOWN", "NOT_RUN") for status in statuses):
        return "UNKNOWN"
    if any(status != "PASS" for status in statuses):
        return "UNKNOWN"
    return "PASS"


def _text_contrast_evidence_problem(root: Path, obs_id: str,
                                    manifest: dict[str, Any]) -> str | None:
    """Check that the named evidence file belongs to this observation and matches it."""
    summary = manifest.get("text_contrast")
    if not isinstance(summary, dict):
        return "The manifest has no text-contrast evidence record."
    evidence = summary.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip():
        return "The manifest does not name a text-contrast evidence file."
    project = root.expanduser().resolve()
    relative = Path(evidence)
    if relative.is_absolute():
        return "Text-contrast evidence path is not project-relative."
    path = (project / relative).resolve()
    try:
        path.relative_to(project)
    except ValueError:
        return "Text-contrast evidence path escapes the project."
    if not path.is_file():
        return f"Text-contrast evidence file is missing: {evidence}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"Text-contrast evidence file cannot be read: {evidence}"
    if not isinstance(payload, dict):
        return "Text-contrast evidence file is not a JSON object."
    if payload.get("observation") != obs_id:
        return "Text-contrast evidence belongs to a different observation."
    aggregate = text_contrast_status(manifest)
    if payload.get("overall_status") != aggregate:
        return "Text-contrast evidence does not match the current manifest."
    if summary.get("overall_status") != aggregate:
        return "Text-contrast summary does not match the current manifest."
    summary_viewports = summary.get("viewports")
    evidence_viewports = payload.get("viewports")
    if not isinstance(summary_viewports, dict) or not isinstance(evidence_viewports, dict):
        return "Text-contrast evidence has no per-viewport results."
    viewports = manifest.get("viewports") or {}
    for vp in _expected_text_contrast_viewports(manifest):
        item = viewports.get(vp)
        recorded = item.get("text_contrast") if isinstance(item, dict) else None
        expected = recorded.get("status", "UNKNOWN") if isinstance(recorded, dict) else "NOT_RUN"
        summary_vp = summary_viewports.get(vp)
        recorded_summary = summary_vp.get("status") if isinstance(summary_vp, dict) else None
        if recorded_summary != expected:
            return f"Text-contrast summary for {vp} does not match the current manifest."
        evidence_vp = evidence_viewports.get(vp)
        recorded_evidence = evidence_vp.get("status") if isinstance(evidence_vp, dict) else None
        if recorded_evidence != expected:
            return f"Text-contrast evidence for {vp} does not match the current manifest."
    return None


def record_text_contrast_evidence(root: Path, obs_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """Write machine-readable and human-readable text-contrast evidence for one observation."""
    project = root.expanduser().resolve()
    base = project / ".aestitch" / "observations" / obs_id
    overall = text_contrast_status(manifest)
    payload = {
        "schema_version": 1,
        "observation": obs_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall_status": overall,
        "thresholds": TEXT_CONTRAST_THRESHOLDS,
        "large_text_rule": "font-size >= 24px, or >= 18.66px with weight >= 700",
        "scope": "initial static page load at the captured viewports; interaction states are not measured",
        "not_covered": list(TEXT_CONTRAST_NOT_COVERED),
        "expected_viewports": _expected_text_contrast_viewports(manifest),
        "viewports": {vp: item.get("text_contrast")
                      for vp, item in manifest.get("viewports", {}).items()
                      if isinstance(item, dict) and isinstance(item.get("text_contrast"), dict)},
        "caveat": "Passing text contrast is not a full accessibility audit, a design approval or an aesthetic score.",
    }
    json_path = base / "text-contrast.json"
    md_path = base / "text-contrast.md"
    temp = json_path.with_name(json_path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, json_path)
    md_path.write_text(text_contrast_markdown(payload), encoding="utf-8")
    manifest["text_contrast"] = {
        "overall_status": overall,
        "thresholds": TEXT_CONTRAST_THRESHOLDS,
        "scope": payload["scope"],
        "not_covered": list(TEXT_CONTRAST_NOT_COVERED),
        "evidence": json_path.relative_to(project).as_posix(),
        "summary": md_path.relative_to(project).as_posix(),
        "viewports": {vp: {"status": (item or {}).get("status", "UNKNOWN"),
                           "counts": (item or {}).get("counts", {})}
                      for vp, item in payload["viewports"].items()},
    }
    return manifest["text_contrast"]


def text_contrast_markdown(payload: dict[str, Any]) -> str:
    lines = [f"# Rendered text contrast — {payload['observation']}", "",
             f"Overall: **{payload['overall_status']}**", "",
             f"Scope: {payload['scope']}.", "",
             "Thresholds: normal text 4.5:1; large text 3:1 "
             f"({payload['large_text_rule']}).", "",
             "A FAIL or UNKNOWN result must not be reported as a passing readability check. "
             "This is not a full accessibility audit or an aesthetic score.", ""]
    for viewport, item in payload["viewports"].items():
        counts = item.get("counts", {})
        context = item.get("scope", {})
        lines += [f"## {viewport} — {item.get('status', 'UNKNOWN')}", "",
                  f"- Measured: {counts.get('measured', 0)}; PASS {counts.get('pass', 0)}; "
                  f"FAIL {counts.get('fail', 0)}; UNKNOWN {counts.get('unknown', 0)}",
                  f"- Not rendered / visually hidden: {counts.get('skipped_not_rendered', 0)} / "
                  f"{counts.get('skipped_visually_hidden', 0)}",
                  f"- State: {context.get('state', 'unknown')}"]
        if counts.get("svg_text_not_covered"):
            lines.append(f"- SVG text not covered: {counts['svg_text_not_covered']}")
        flagged = [row for row in item.get("rows", []) if row.get("status") != "PASS"]
        if flagged:
            lines += ["", "| Status | Ratio | Threshold | Selector | Text | Reason |",
                      "| --- | --- | --- | --- | --- | --- |"]
            for row in flagged[:40]:
                text = str(row.get("text", "")).replace("|", "\\|")[:60]
                reason = str(row.get("reason") or "below threshold").replace("|", "\\|")[:80]
                ratio = "unknown" if row.get("ratio") is None else f"{row['ratio']}:1"
                lines.append(f"| {row.get('status')} | {ratio} | {row.get('threshold')}:1 | "
                             f"`{row.get('selector', '?')}` | {text} | {reason} |")
        lines.append("")
    return "\n".join(lines)


def text_contrast_gate(root: Path, obs_id: str) -> tuple[str, str]:
    manifest = load(state_dir(root) / "observations" / slug(obs_id) / "manifest.json", None)
    if not isinstance(manifest, dict):
        raise ValueError("Observation not found")
    status = text_contrast_status(manifest)
    if status == "NOT_RUN":
        return status, "Rendered text contrast was not run for this observation; it cannot be reported as passing."
    observation_status = manifest.get("status", "missing")
    if observation_status != "completed":
        return status, (f"Observation status is {observation_status}, not completed; "
                        "its measurements cannot be reported as passing.")
    viewports = manifest.get("viewports") or {}
    missing = [vp for vp in _expected_text_contrast_viewports(manifest)
               if not isinstance(viewports.get(vp), dict)
               or not isinstance(viewports[vp].get("text_contrast"), dict)]
    if missing:
        return status, ("Rendered text contrast has no result for expected viewport(s): "
                        + ", ".join(missing) + "; it cannot be reported as passing.")
    if status == "FAIL":
        return status, "At least one measured text element is below its applicable threshold."
    if status == "UNKNOWN":
        return status, "Coverage is incomplete or some backgrounds could not be measured reliably."
    problem = _text_contrast_evidence_problem(root, obs_id, manifest)
    if problem:
        return "UNKNOWN", problem
    return status, ("All expected viewports were measured and every measured text element "
                    "met the applicable rendered contrast threshold.")


def observe_report(root: Path, obs_id: str) -> str:
    manifest = load(state_dir(root) / "observations" / slug(obs_id) / "manifest.json", None)
    if not isinstance(manifest, dict):
        raise ValueError("Observation not found")
    lines = [f"# Observation: {manifest.get('id', obs_id)}", "",
             f"Status: {manifest.get('status', 'legacy/unknown')}",
             f"Source: `{manifest.get('source', 'unknown')}`", "",
             "Facts below are captured from a rendered browser page. No aesthetic conclusion is inferred.", ""]
    if manifest.get("status") == "failed":
        lines.extend([f"- Failure: {manifest.get('error', 'not recorded')}",
                      f"- Failed at: {manifest.get('failed_at', 'not recorded')}", ""])
    elif manifest.get("status") == "in_progress":
        lines.extend(["- Capture did not finish; treat this observation as incomplete.", ""])
    for vp, v in manifest.get("viewports", {}).items():
        ev = v.get("evidence") or {}
        lines.extend([f"## {vp}", "", f"- Title: {ev.get('title', 'unknown')}",
                      f"- Document height: {ev.get('documentHeight', 'unknown')}",
                      f"- Horizontal overflow: {ev.get('horizontalOverflow', 'unknown')}",
                      f"- Visible controls: {len(ev.get('controls', []))}"])
        ctx = v.get("capture_context") or manifest.get("capture_context")
        if isinstance(ctx, dict) and ctx:
            viewport = ctx.get("viewport") or ev.get("viewport") or {}
            size = f"{viewport.get('width', '?')}x{viewport.get('height', '?')}"
            screenshots = ctx.get("screenshots") or {}
            animations = ctx.get("animations") or screenshots.get("animations", "unknown")
            lines.append(f"- Capture context: viewport={size}; reduced_motion={ctx.get('reduced_motion', 'unknown')}; animations={animations}")
        else:
            lines.append("- Capture context: legacy/unknown (manifest predates capture context)")
        scope = v.get("evidence_scope") or manifest.get("evidence_scope")
        lines.append(f"- Evidence scope: {', '.join(scope) if isinstance(scope, list) else (scope or 'legacy/unknown')}")
        not_observed = v.get("not_observed") or manifest.get("not_observed")
        if not_observed:
            lines.append(f"- Not observed: {', '.join(not_observed)}")
        tc = v.get("text_contrast")
        if isinstance(tc, dict):
            counts = tc.get("counts", {})
            incomplete = "" if manifest.get("status") == "completed" else "; capture did not complete"
            lines.append(f"- Text contrast: {tc.get('status', 'UNKNOWN')} "
                         f"(measured {counts.get('measured', 0)}; PASS {counts.get('pass', 0)}; "
                         f"FAIL {counts.get('fail', 0)}; UNKNOWN {counts.get('unknown', 0)})"
                         f"{incomplete}")
            for row in [r for r in tc.get("rows", []) if r.get("status") != "PASS"][:10]:
                ratio = "unknown" if row.get("ratio") is None else f"{row['ratio']}:1"
                lines.append(f"  - {row.get('status')}: {ratio} (threshold {row.get('threshold')}:1) "
                             f"`{row.get('selector', '?')}` “{row.get('text', '')}” — "
                             f"{row.get('reason') or 'below threshold'}")
        frames = v.get("frames", [])
        lines.extend([f"- Frames: {', '.join(f.get('path', '?') for f in frames)}", "",
                      "### Observable anchor geometry and CSS", ""])
        for a in ev.get("anchors", [])[:24]:
            lines.append(f"- `{a.get('key', '?')}`: {a.get('rect', {})}; font={(a.get('style') or {}).get('fontFamily')}; size={(a.get('style') or {}).get('fontSize')}")
        lines.append("")
    aggregate = text_contrast_status(manifest)
    if aggregate != "NOT_RUN":
        lines += ["## Rendered text contrast summary", "",
                  f"- Overall: **{aggregate}**",
                  "- Scope: initial static page load; interaction, hover, focus, disabled, "
                  "pseudo-element text and SVG/canvas text are not measured.",
                  "- A FAIL, UNKNOWN or NOT_RUN result must not be reported as a passing readability check.",
                  "- Evidence: `text-contrast.json` / `text-contrast.md` in this observation.", ""]
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


def _fit_observation_id(base: str, suffix: str) -> str:
    """Keep generated observation IDs within the shared slug limit.

    Long Concept IDs share their prefix after truncation, so a short hash of the
    full base is appended whenever truncation happens; otherwise two different
    Concepts could collide on the same observation ID.
    """
    candidate = base + suffix
    if len(candidate) <= 63:
        return candidate
    digest_part = sha1(base.encode("utf-8")).hexdigest()[:8]
    room = 63 - len(suffix) - len(digest_part) - 1
    stem = base[:room].rstrip("-_") or "concept"
    return stem + "-" + digest_part + suffix


def _next_concept_observation_id(state: Path, concept_id: str, rec: dict[str, Any]) -> str:
    base = f"concept-{slug(concept_id)}"
    used = set(rec.get("observation_ids") or [])
    if rec.get("observation_id"):
        used.add(rec["observation_id"])
    candidate = base
    index = 1
    while candidate in used or (state / "observations" / candidate).exists():
        index += 1
        candidate = _fit_observation_id(base, f"-r{index}")
    return candidate


class ObservationReserved(ValueError):
    """Raised when another writer already owns the requested observation ID."""


def concept_render(root: Path, concept_id: str, viewport: str) -> dict[str, Any]:
    state = state_dir(root)
    concept_dir = _concept_path(state, concept_id)
    if not (concept_dir / "concept.json").is_file():
        raise ValueError("Concept does not exist")
    # Single writer per Concept, enforced across processes. Concurrent renders
    # fail clearly instead of racing on the same observation ID or pointer.
    with _concept_write_lock(concept_dir):
        rec = concept_load(root, concept_id)
        obs = None
        for _ in range(5):
            obs_id = _next_concept_observation_id(state, concept_id, rec)
            try:
                obs = observe(root, obs_id, None, str(root.resolve() / rec["prototype"]),
                              viewport, 1, overwrite=False, claim=True)
                break
            except ObservationReserved:
                continue
        if obs is None:
            raise ValueError("Could not reserve a fresh observation ID for this concept")
        history = list(rec.get("observation_ids") or [])
        old = rec.get("observation_id")
        if old and old not in history:
            history.append(old)
        if obs_id not in history:
            history.append(obs_id)
        rec["observation_ids"] = history
        rec["observation_id"] = obs_id
        rec["observation_status"] = "completed"
        save(concept_dir / "concept.json", rec)
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

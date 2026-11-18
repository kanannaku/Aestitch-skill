#!/usr/bin/env python3
"""Aestitch v0.1: local-first design memory and visual change evidence.

Python >=3.10. Browser capture optionally requires playwright + Chromium.
Pixel comparison optionally requires Pillow. No network calls except user-requested
browser navigation. The program does not modify application source code.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

VERSION = "0.1.0"
AXES = ("composition", "typography", "color", "motion", "interaction", "content", "other")
VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}
TAGS = ("baseline", "candidate")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"Missing {path}. Run `init` first.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def project_paths(root: Path) -> tuple[Path, Path]:
    root = root.expanduser().resolve()
    return root, root / ".aestitch"


def init(root: Path) -> int:
    root, state = project_paths(root)
    if not root.is_dir():
        raise ValueError(f"Project directory not found: {root}")
    state.mkdir(exist_ok=True)
    profile = state / "profile.json"
    if not profile.exists():
        write_json(profile, {"schema_version": 1, "project": root.name, "principles": [], "feedback": []})
        print(f"Created {profile}")
    else:
        print(f"Kept existing {profile}")
    ignore = state / ".gitignore"
    if not ignore.exists():
        write_text(ignore, "# Keep screenshots and personal design preferences local by default\n*\n!.gitignore\n")
    print("Aestitch initialized. Private profile and screenshots stay under .aestitch/.")
    return 0


def record(root: Path, kind: str, axis: str, note: str, context: str) -> int:
    if not note.strip():
        raise ValueError("Feedback must include a non-empty --note.")
    _, state = project_paths(root)
    profile = read_json(state / "profile.json")
    feedback = profile.setdefault("feedback", [])
    if not isinstance(feedback, list):
        raise ValueError("profile.feedback must be an array")
    item = {"id": str(uuid4()), "kind": kind, "axis": axis,
            "note": note.strip(), "context": context.strip(),
            "source": "user-confirmed", "created_at": timestamp()}
    feedback.append(item)
    write_json(state / "profile.json", profile)
    print(f"Recorded {kind} / {axis}: {note.strip()}")
    return 0


def brief(root: Path, output: str | None = None) -> int:
    _, state = project_paths(root)
    profile = read_json(state / "profile.json")
    prefs = profile.get("feedback", [])
    if not isinstance(prefs, list):
        raise ValueError("profile.feedback must be an array")
    lines = ["# Aestitch — project design brief", "", "Generated from explicitly user-confirmed feedback. Not a model-inferred aesthetic score.", ""]
    if not prefs:
        lines += ["No preferences recorded yet. Ask the user about one concrete visual decision before making major changes.", ""]
    else:
        for kind, heading in (("prefer", "Preserve / favor"), ("avoid", "Avoid")):
            lines += [f"## {heading}", ""]
            matches = [x for x in prefs if isinstance(x, dict) and x.get("kind") == kind]
            if matches:
                for item in matches:
                    context = f" (context: {item['context']})" if item.get("context") else ""
                    lines.append(f"- **{item.get('axis', 'other')}** — {item.get('note', '')}{context}")
            else:
                lines.append("- None recorded")
            lines.append("")
    lines += ["## Agent instructions", "", "Use these as evidence, not universal style rules. Preserve the current design's intent, ask before overriding explicit user decisions, and review actual screenshots.", ""]
    content = "\n".join(lines)
    if output:
        out = Path(output).expanduser().resolve()
        write_text(out, content)
        print(f"Wrote {out}")
    else:
        print(content)
    return 0


def validate_url(url: str, allow_remote: bool) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only http(s) URLs with a hostname and no embedded credentials are supported.")
    if not allow_remote and parsed.hostname.lower() not in ("localhost", "127.0.0.1", "::1", "[::1]"):
        raise ValueError("Remote capture is disabled by default. Use --allow-remote only for a trusted site.")
    return url


def validate_html_file(root: Path, path: str) -> Path:
    root = root.expanduser().resolve()
    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file() or candidate.suffix.lower() not in (".html", ".htm"):
        raise ValueError("--html-file must be an existing HTML file")
    if not candidate.is_relative_to(root):
        raise ValueError("--html-file must be inside the target project root")
    return candidate


def capture(root: Path, url: str | None, html_file: str | None, tag: str, viewport: str, wait_ms: int,
            allow_remote: bool, overwrite_baseline: bool) -> int:
    if html_file is None:
        assert url is not None
        validate_url(url, allow_remote)
    else:
        validate_html_file(root, html_file)
    if wait_ms < 0 or wait_ms > 10000:
        raise ValueError("--wait-ms must be between 0 and 10000")
    _, state = project_paths(root)
    read_json(state / "profile.json")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ValueError("Browser capture requires `pip install playwright` and `python -m playwright install chromium`.") from exc
    chosen = list(VIEWPORTS) if viewport == "both" else [viewport]
    destinations = [(vp, state / "screenshots" / tag / f"{vp}.png") for vp in chosen]
    if tag == "baseline" and not overwrite_baseline:
        existing = [str(p) for _, p in destinations if p.exists()]
        if existing:
            raise ValueError("Refusing to overwrite the baseline: " + ", ".join(existing) + ". Use --overwrite-baseline only after explicit approval.")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True, executable_path=os.environ.get("AESTITCH_CHROMIUM_EXECUTABLE") or None
        )
        try:
            for vp, target in destinations:
                width, height = VIEWPORTS[vp]
                ctx = browser.new_context(viewport={"width": width, "height": height},
                                          device_scale_factor=1, reduced_motion="reduce",
                                          is_mobile=(vp == "mobile"), has_touch=(vp == "mobile"))
                page = ctx.new_page()
                console_errors: list[str] = []
                page.on("pageerror", lambda exc: console_errors.append(str(exc)[:300]))
                page.on("console", lambda msg: console_errors.append(msg.text[:300]) if msg.type == "error" else None)
                try:
                    if html_file:
                        # Offline prototype mode; only inline styles/resources are reliable.
                        response = None
                        page.set_content(validate_html_file(root, html_file).read_text(encoding="utf-8"),
                                         wait_until="domcontentloaded", timeout=20000)
                    else:
                        response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(wait_ms)
                    diag = page.evaluate("""() => ({
                        title: document.title,
                        documentWidth: document.documentElement.scrollWidth,
                        viewportWidth: window.innerWidth,
                        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 2,
                        imagesMissingAlt: document.querySelectorAll('img:not([alt])').length
                    })""")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(target), full_page=True, animations="disabled")
                    metadata = {"version": 1, "captured_at": timestamp(), "tag": tag, "viewport": vp,
                                "url": url or "offline-html", "size": [width, height], "http_status": response.status if response else None,
                                "diagnostics": diag, "page_errors": console_errors[:20]}
                    write_json(target.with_suffix(".json"), metadata)
                    print(f"Captured {tag}/{vp}: {target}")
                finally:
                    ctx.close()
        finally:
            browser.close()
    return 0


def compare_images(baseline: Path, candidate: Path, diff_output: Path,
                   pixel_threshold: int) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError as exc:
        raise ValueError("Image comparison requires Pillow: `pip install pillow`.") from exc
    with Image.open(baseline) as img_a, Image.open(candidate) as img_b:
        a, b = img_a.convert("RGB"), img_b.convert("RGB")
    if a.size != b.size:
        return {"status": "dimension_mismatch", "baseline_size": list(a.size),
                "candidate_size": list(b.size), "changed_pct": None,
                "mean_abs_channel_diff": None,
                "note": "Page dimensions changed. Pixel comparison skipped; inspect screenshots manually."}
    difference = ImageChops.difference(a, b)
    # A single color channel can change significantly while grayscale luminance
    # barely moves (e.g. a hue shift). Threshold the maximum channel delta.
    red, green, blue = difference.split()
    maximum_delta = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    changed = maximum_delta.point(lambda value: 255 if value > pixel_threshold else 0)
    histogram = changed.histogram()
    pixels_changed = sum(histogram[1:])
    total = a.width * a.height
    mean_diff = sum(ImageStat.Stat(difference).mean) / 3.0
    diff_output.parent.mkdir(parents=True, exist_ok=True)
    # Highlight changed pixels while preserving candidate context.
    overlay = Image.new("RGB", b.size, (232, 64, 114))
    highlighted = Image.blend(b, overlay, 0.55)
    output = Image.composite(highlighted, b, changed)
    output.save(diff_output)
    return {"status": "compared", "baseline_size": list(a.size),
            "candidate_size": list(b.size),
            "changed_pct": round(100 * pixels_changed / total, 3),
            "mean_abs_channel_diff": round(mean_diff, 3), "diff_image": str(diff_output)}


def guard(root: Path, warn_change_pct: float, pixel_threshold: int) -> int:
    if not 0 <= warn_change_pct <= 100:
        raise ValueError("--warn-change-pct must be between 0 and 100")
    if not 0 <= pixel_threshold <= 255:
        raise ValueError("--pixel-threshold must be between 0 and 255")
    _, state = project_paths(root)
    read_json(state / "profile.json")
    checks = []
    report_dir = state / "reports"
    for viewport in VIEWPORTS:
        source = state / "screenshots" / "baseline" / f"{viewport}.png"
        target = state / "screenshots" / "candidate" / f"{viewport}.png"
        if not source.exists() or not target.exists():
            checks.append({"viewport": viewport, "status": "missing_evidence",
                           "missing": [str(p) for p in (source, target) if not p.exists()]})
            continue
        check = compare_images(source, target, report_dir / f"diff-{viewport}.png", pixel_threshold)
        check["viewport"] = viewport
        for label, image in (("baseline", source), ("candidate", target)):
            meta = image.with_suffix(".json")
            if meta.is_file():
                check[f"{label}_diagnostics"] = read_json(meta).get("diagnostics", {})
                check[f"{label}_page_errors"] = read_json(meta).get("page_errors", [])
        if check["status"] == "compared":
            check["status"] = "needs_review" if check["changed_pct"] > warn_change_pct else "change_observed"
        checks.append(check)
    report = {"schema_version": 1, "generated_at": timestamp(),
              "disclaimer": "Pixel difference is not aesthetic quality. A human or vision-enabled agent must review intent and meaning.",
              "threshold": {"warn_change_pct": warn_change_pct, "pixel_threshold": pixel_threshold},
              "checks": checks}
    write_json(report_dir / "guard-report.json", report)
    lines = ["# Aestitch — visual change report", "", f"Generated: {report['generated_at']}", "",
             "**This detects changes, not beauty or design quality.** Review screenshots and the project's taste brief before accepting a redesign.", ""]
    for check in checks:
        lines += [f"## {check['viewport']} — {check['status']}", ""]
        if check.get("changed_pct") is not None:
            lines.append(f"- Changed pixels: {check['changed_pct']}% (threshold per-pixel: {pixel_threshold})")
            lines.append(f"- Mean absolute channel difference: {check['mean_abs_channel_diff']}/255")
            lines.append(f"- Diff: `diff-{check['viewport']}.png`")
        if check.get("missing"):
            lines.append(f"- Missing: {', '.join(check['missing'])}")
        if check.get("status") == "dimension_mismatch":
            lines.append(f"- Baseline: {check['baseline_size']} / Candidate: {check['candidate_size']}")
        bdiag, cdiag = check.get("baseline_diagnostics", {}), check.get("candidate_diagnostics", {})
        if bdiag or cdiag:
            lines.append(f"- Horizontal overflow (before → after): {bdiag.get('horizontalOverflow', '?')} → {cdiag.get('horizontalOverflow', '?')}")
            lines.append(f"- Images missing alt (before → after): {bdiag.get('imagesMissingAlt', '?')} → {cdiag.get('imagesMissingAlt', '?')}")
        if check.get("candidate_page_errors"):
            lines.append(f"- Candidate page errors: {len(check['candidate_page_errors'])}")
        lines.append("")
    lines += ["## Human/agent review checklist", "", "- [ ] Does the new design preserve approved composition, typography and hierarchy?",
              "- [ ] Are changes intentional, not accidental UI drift?",
              "- [ ] Are desktop and mobile layout/interaction still usable?",
              "- [ ] Were dynamic regions, animations and font loading controlled?",
              "- [ ] Are visual differences explained and approved?", ""]
    write_text(report_dir / "guard-report.md", "\n".join(lines))
    print(f"Wrote {report_dir / 'guard-report.md'}")
    for check in checks:
        print(f"{check['viewport']}: {check['status']}" +
              (f" ({check['changed_pct']}% changed)" if check.get("changed_pct") is not None else ""))
    return 0 if all(c["status"] not in ("missing_evidence", "dimension_mismatch") for c in checks) else 2


def doctor() -> int:
    print(f"Aestitch {VERSION} | Python {sys.version.split()[0]}")
    for name in ("PIL", "playwright"):
        try:
            __import__(name)
            print(f"{name}: installed")
        except ImportError:
            print(f"{name}: not installed (optional)")
    chromium = os.environ.get("AESTITCH_CHROMIUM_EXECUTABLE")
    if chromium:
        print(f"Chromium override: {'available' if Path(chromium).is_file() else 'missing'} ({chromium})")
    elif __import__("importlib").util.find_spec("playwright"):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            print(f"Playwright Chromium: {'available' if Path(pw.chromium.executable_path).is_file() else 'missing (run python -m playwright install chromium)'}")
    print("Capture: install playwright and Chromium. Compare: install Pillow.")
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aestitch", description="Local-first design memory and visual change guardian")
    parser.add_argument("--root", default=".", help="Target website project root (default: current directory)")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Create private project design state")
    p = sub.add_parser("record", help="Record explicitly confirmed design feedback")
    p.add_argument("--kind", choices=("prefer", "avoid"), required=True)
    p.add_argument("--axis", choices=AXES, required=True)
    p.add_argument("--note", required=True)
    p.add_argument("--context", default="", help="Scope: homepage, light theme, etc.")
    p = sub.add_parser("brief", help="Render an agent-readable brief from user-confirmed feedback")
    p.add_argument("--output", help="Optional markdown output path")
    p = sub.add_parser("capture", help="Capture real browser screenshots of the current page")
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="Capture a running web page (localhost by default)")
    source.add_argument("--html-file", help="Render a self-contained HTML file within the project (offline prototype mode)")
    p.add_argument("--tag", choices=TAGS, required=True)
    p.add_argument("--viewport", choices=(*VIEWPORTS, "both"), default="both")
    p.add_argument("--wait-ms", type=int, default=700)
    p.add_argument("--allow-remote", action="store_true")
    p.add_argument("--overwrite-baseline", action="store_true")
    p = sub.add_parser("guard", help="Compare baseline and candidate screenshots")
    p.add_argument("--warn-change-pct", type=float, default=12.0)
    p.add_argument("--pixel-threshold", type=int, default=24)
    sub.add_parser("doctor", help="Check optional dependencies")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    root = Path(args.root)
    try:
        if args.command == "init":
            return init(root)
        if args.command == "record":
            return record(root, args.kind, args.axis, args.note, args.context)
        if args.command == "brief":
            return brief(root, args.output)
        if args.command == "capture":
            return capture(root, args.url, args.html_file, args.tag, args.viewport, args.wait_ms,
                           args.allow_remote, args.overwrite_baseline)
        if args.command == "guard":
            return guard(root, args.warn_change_pct, args.pixel_threshold)
        if args.command == "doctor":
            return doctor()
    except (ValueError, OSError) as exc:
        print(f"Aestitch error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

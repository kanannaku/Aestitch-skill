"""Aestitch structured references, taste comparisons, design contracts and change scope.

All operations are local, deterministic and dependency-free. No reference URL is fetched.
User taste isn't inferred: recorded selections are observations, never objective rankings.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

VALID_CHOICES = {"left", "right", "both", "neither", "unsure"}
SOURCE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".css", ".scss", ".html", ".htm", ".json", ".py", ".md", ".yml", ".yaml", ".toml", ".vue", ".svelte", ".c", ".h", ".cpp", ".hpp"}
SKIP_DIRS = {".git", ".aestitch", "node_modules", ".next", "dist", "build", "coverage", ".venv", "venv", "__pycache__", ".turbo", ".cache", "target"}
MAX_TRACKED_FILE = 2 * 1024 * 1024
MAX_REF_IMAGE = 15 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def state_dir(root: Path) -> Path:
    state = root.expanduser().resolve() / ".aestitch"
    if not (state / "profile.json").is_file():
        raise ValueError("Run `aestitch init` first.")
    return state


def load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Aestitch state file: {path.name}: {exc}") from exc


def save(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(text: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", text):
        raise ValueError("Identifier must be 1–63 lower-case letters, numbers, _ or -, starting with a letter/number")
    return text


def _ref_db(state: Path) -> Path:
    return state / "references.json"


def add_reference(root: Path, label: str, url: str | None, image: str | None,
                  context: str, observation: str, focus: str) -> dict[str, Any]:
    state = state_dir(root)
    if not label.strip() or (url is None) == (image is None):
        raise ValueError("Provide a non-empty label and exactly one of --url or --image.")
    ref_id = "ref-" + uuid4().hex[:12]
    item: dict[str, Any] = {"id": ref_id, "label": label.strip(), "context": context.strip(),
                            "focus": focus.strip(), "observation": observation.strip(),
                            "observation_status": "unverified", "created_at": now()}
    if url is not None:
        p = urlsplit(url)
        if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
            raise ValueError("--url must be a valid http(s) URL without embedded credentials.")
        if len(url) > 2048:
            raise ValueError("--url is too long.")
        item.update({"source_type": "url", "source": url, "accessed": False})
    else:
        source = Path(image or "").expanduser().resolve()
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp") or not source.is_file():
            raise ValueError("--image must be an existing png, jpeg or webp file.")
        if source.stat().st_size > MAX_REF_IMAGE:
            raise ValueError("Reference image exceeds 15MB.")
        with source.open("rb") as handle:
            header = handle.read(16)
        if not (header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8\xff") or header.startswith(b"RIFF") and header[8:12] == b"WEBP"):
            raise ValueError("Image signature does not match a supported image format.")
        asset = state / "assets" / f"{ref_id}{source.suffix.lower()}"
        asset.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, asset)
        item.update({"source_type": "image", "source": f"assets/{asset.name}", "sha256": digest(asset)})
    db = load(_ref_db(state), [])
    if not isinstance(db, list):
        raise ValueError("references.json must be an array")
    db.append(item)
    save(_ref_db(state), db)
    return item


def list_references(root: Path) -> list[dict[str, Any]]:
    data = load(_ref_db(state_dir(root)), [])
    if not isinstance(data, list):
        raise ValueError("references.json must be an array")
    return data


def taste_compare(root: Path, left: str, right: str, choice: str, why: str, context: str,
                  relative_preference: str = "unknown", acceptance: str = "unknown") -> dict[str, Any]:
    state = state_dir(root)
    if relative_preference not in ("left", "right", "equal", "unknown"):
        raise ValueError("Invalid relative preference")
    if acceptance not in ("left", "right", "both", "neither", "unknown"):
        raise ValueError("Invalid absolute acceptance")
    if choice not in VALID_CHOICES or left == right:
        raise ValueError("Choose two different references and one valid preference outcome.")
    known = {r.get("id") for r in list_references(root)}
    if left not in known or right not in known:
        raise ValueError("Both --left and --right must refer to saved reference IDs")
    item = {"id": "choice-" + uuid4().hex[:12], "left": left, "right": right,
            "choice": choice, "relative_preference": relative_preference,
            "absolute_acceptance": acceptance,
            "why": why.strip(), "context": context.strip(),
            "source": "user-reported", "recorded_at": now()}
    path = state / "comparisons.json"
    comparisons = load(path, [])
    if not isinstance(comparisons, list):
        raise ValueError("comparisons.json must be an array")
    comparisons.append(item)
    save(path, comparisons)
    return item


def taste_report(root: Path) -> str:
    state = state_dir(root)
    refs = {r["id"]: r for r in list_references(root)}
    comparisons = load(state / "comparisons.json", [])
    if not isinstance(comparisons, list):
        raise ValueError("comparisons.json must be an array")
    lines = ["# Aestitch — taste discovery evidence", "", "These are contextual, user-reported choices. No stable style identity or aesthetic score is inferred.", ""]
    if not comparisons:
        lines += ["No comparisons yet. Present two genuinely different visual references and allow left/right/both/neither/unsure.", ""]
    for c in comparisons:
        l, r = refs.get(c.get("left"), {}), refs.get(c.get("right"), {})
        lines.append(f"- **{l.get('label', c.get('left'))}** vs **{r.get('label', c.get('right'))}**: {c.get('choice')} (context: {c.get('context') or 'unspecified'})")
        if c.get("relative_preference", "unknown") != "unknown":
            lines.append(f"  - Relative preference: {c['relative_preference']}")
        if c.get("absolute_acceptance", "unknown") != "unknown":
            lines.append(f"  - Absolute acceptance: {c['absolute_acceptance']}")
        if c.get("why"):
            lines.append(f"  - User's words: {c['why']}")
    lines += ["", "## Suggested next step", "", "Form a *hypothesis*, then compare designs that isolate one variable (layout, type, color, motion). Do not mark the hypothesis user-confirmed without explicit approval.", ""]
    return "\n".join(lines)


def _contract_path(state: Path, page: str) -> Path:
    return state / "contracts" / f"{slug(page)}.json"


def contract_create(root: Path, page: str, goal: str, direction: str, scope: str,
                    reference_ids: list[str]) -> dict[str, Any]:
    state = state_dir(root)
    path = _contract_path(state, page)
    if path.exists():
        raise ValueError("A contract already exists for this page. Edit deliberately; never silently overwrite it.")
    if not goal.strip() or not direction.strip() or not scope.strip():
        raise ValueError("--goal, --direction and --scope must be non-empty")
    known = {r["id"] for r in list_references(root)}
    if any(ref not in known for ref in reference_ids):
        raise ValueError("Unknown reference ID in --reference")
    contract = {"schema_version": 1, "page": page, "status": "draft", "goal": goal.strip(),
                "creative_direction": direction.strip(), "implementation_scope": scope.strip(),
                "references": list(dict.fromkeys(reference_ids)),
                "design_tokens": {}, "must_preserve": [], "must_avoid": [],
                "responsive_viewports": ["desktop", "mobile"], "interaction_states": [],
                "visual_evidence": [], "approval": None, "created_at": now()}
    save(path, contract)
    return contract


def contract_load(root: Path, page: str) -> dict[str, Any]:
    path = _contract_path(state_dir(root), page)
    obj = load(path, None)
    if not isinstance(obj, dict):
        raise ValueError("No contract for this page. Run `contract create` first.")
    return obj


def contract_approve(root: Path, page: str, evidence: str, note: str, user_confirmed: bool) -> dict[str, Any]:
    if not user_confirmed:
        raise ValueError("Require --user-confirmed after explicit user approval; an agent must not self-approve.")
    if not note.strip():
        raise ValueError("Approval requires a concrete --note describing the accepted direction")
    state = state_dir(root)
    contract = contract_load(root, page)
    if contract["status"] == "approved":
        raise ValueError("This contract is already approved; do not overwrite its approval record.")
    img = Path(evidence).expanduser().resolve()
    project_root = root.expanduser().resolve()
    if not img.is_file() or img.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Provide an existing screenshot/prototype image as --evidence")
    if not img.is_relative_to(project_root):
        raise ValueError("Evidence must be within the target project, including its private .aestitch directory")
    contract["visual_evidence"].append({"path": img.relative_to(project_root).as_posix(), "sha256": digest(img)})
    contract["status"] = "approved"
    contract["approval"] = {"source": "explicit-user-confirmation", "note": note.strip(), "approved_at": now()}
    save(_contract_path(state, page), contract)
    return contract


def contract_markdown(obj: dict[str, Any]) -> str:
    lines = [f"# Aestitch design contract — {obj['page']}", "", f"**Status:** {obj['status']} — not a guarantee of visual fidelity", "",
             "## Goal", obj["goal"], "", "## Creative direction", obj["creative_direction"], "",
             "## Allowed implementation scope", obj["implementation_scope"], "", "## References", ""]
    lines += [f"- `{r}`" for r in obj.get("references", [])] or ["- None"]
    lines += ["", "## Preserved decisions", ""]
    lines += [f"- {x}" for x in obj.get("must_preserve", [])] or ["- None explicitly locked"]
    lines += ["", "## Avoid", ""]
    lines += [f"- {x}" for x in obj.get("must_avoid", [])] or ["- None explicitly locked"]
    lines += ["", "## Design tokens", "", "```json", json.dumps(obj.get("design_tokens", {}), indent=2, ensure_ascii=False), "```", ""]
    lines += ["## Evidence", ""]
    lines += [f"- `{x['path']}` (sha256: `{x['sha256']}`)" for x in obj.get("visual_evidence", [])] or ["- No evidence yet"]
    lines += ["", "## Implementation handoff", "", "Do not redesign approved decisions during implementation. Compare browser captures with supplied evidence and disclose any approximation or missing information. If status is draft, request a design decision before broad UI changes.", ""]
    return "\n".join(lines)


def _file_manifest(root: Path) -> dict[str, dict[str, Any]]:
    root = root.expanduser().resolve()
    manifest: dict[str, dict[str, Any]] = {}
    for folder, dirs, files in os.walk(root, followlinks=False):
        base = Path(folder)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (base / d).is_symlink())
        for name in sorted(files):
            path = base / name
            if path.is_symlink() or path.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            if path.stat().st_size > MAX_TRACKED_FILE:
                continue
            relative = path.relative_to(root).as_posix()
            manifest[relative] = {"sha256": digest(path), "bytes": path.stat().st_size}
            if len(manifest) > 12000:
                raise ValueError("Too many tracked source files. Narrow the project scope.")
    return manifest


def _dependencies(root: Path) -> list[str]:
    package = root / "package.json"
    if not package.is_file():
        return []
    try:
        manifest = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid package.json") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Invalid package.json structure")
    result = []
    for section in ("dependencies", "devDependencies"):
        entries = manifest.get(section, {})
        if not isinstance(entries, dict):
            raise ValueError(f"package.json {section} must be an object")
        result.extend(f"{section}:{key}" for key in entries)
    return sorted(set(result))


def scope_snapshot(root: Path, tag: str, overwrite: bool) -> dict[str, Any]:
    state = state_dir(root)
    path = state / "snapshots" / (slug(tag) + ".json")
    if path.exists() and not overwrite:
        raise ValueError("Snapshot exists; explicit --overwrite is required.")
    obj = {"schema_version": 1, "tag": tag, "created_at": now(),
           "files": _file_manifest(root), "dependencies": _dependencies(root)}
    save(path, obj)
    return obj


def _safe_prefix(prefix: str) -> str:
    p = prefix.replace("\\", "/").strip("/")
    if not p or p.startswith(".") or any(x in (".", "..") for x in p.split("/")):
        raise ValueError("--allow must be a non-empty project-relative path or directory (no traversal)")
    return p


def scope_check(root: Path, tag: str, allow: list[str], max_added: int,
                max_changed: int, max_deleted: int, max_dependencies: int) -> tuple[dict[str, Any], int]:
    state = state_dir(root)
    snap = load(state / "snapshots" / (slug(tag) + ".json"), None)
    if not isinstance(snap, dict):
        raise ValueError("Missing scope snapshot. Run `scope snapshot --tag ...` before editing.")
    if any(x < 0 for x in (max_added, max_changed, max_deleted, max_dependencies)):
        raise ValueError("Change limits cannot be negative")
    before = snap["files"]
    after = _file_manifest(root)
    new_paths, gone = set(after) - set(before), set(before) - set(after)
    modified = {p for p in set(before) & set(after) if before[p]["sha256"] != after[p]["sha256"]}
    prefixes = [_safe_prefix(p) for p in allow]
    changed_paths = new_paths | gone | modified
    outside = sorted(p for p in changed_paths if prefixes and not any(p == pre or p.startswith(pre + "/") for pre in prefixes))
    deps = sorted(set(_dependencies(root)) - set(snap.get("dependencies", [])))
    reasons = []
    for label, items, limit in (("new files", new_paths, max_added), ("changed files", modified, max_changed),
                                ("deleted files", gone, max_deleted), ("added dependencies", deps, max_dependencies)):
        if len(items) > limit:
            reasons.append(f"{label}: {len(items)} exceeds limit {limit}")
    if changed_paths and not prefixes:
        reasons.append("no approved --allow scope was supplied for changed files")
    if outside:
        reasons.append(f"out-of-scope file changes: {len(outside)}")
    result = {"schema_version": 1, "tag": tag, "checked_at": now(), "status": "review_required" if reasons else "within_budget",
              "added": sorted(new_paths), "modified": sorted(modified), "deleted": sorted(gone),
              "dependencies_added": deps, "out_of_scope": outside, "allow": prefixes,
              "limits": {"added": max_added, "modified": max_changed, "deleted": max_deleted, "dependencies_added": max_dependencies},
              "review_reasons": reasons,
              "note": "A scope check flags changed files, not code quality or aesthetic quality. Verify with tests and browser review."}
    reports = state / "reports"
    save(reports / "scope-report.json", result)
    lines = ["# Aestitch — implementation scope report", "", f"Status: **{result['status']}**", "",
             "This is a review signal, not an automatic aesthetic or code-quality verdict.", ""]
    for category in ("added", "modified", "deleted", "dependencies_added", "out_of_scope", "review_reasons"):
        lines += [f"## {category.replace('_', ' ').title()}", ""]
        lines += [f"- {p}" for p in result[category]] or ["- None"]
        lines.append("")
    (reports).mkdir(exist_ok=True)
    (reports / "scope-report.md").write_text("\n".join(lines), encoding="utf-8")
    return result, 2 if reasons else 0

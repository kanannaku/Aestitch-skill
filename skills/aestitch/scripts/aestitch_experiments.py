"""Local experiment handoff packets: evidence and review, never aesthetic scores."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")
DECISIONS = {"unreviewed", "neither", "left", "right", "both", "unsure"}
RELATIVE = {"unknown", "left", "right", "equal"}
# Agent-recorded classes. `user_confirmed` is deliberately absent: only the
# review workflow may record user confirmation, and even then it is a local
# self-declaration, not identity verification.
RECORDABLE_CLASSES = {"observed", "measured", "inferred", "unverified"}
KNOWN_CLASSES = RECORDABLE_CLASSES | {"user_confirmed"}
REVIEW_SOURCES = {"user_direct", "agent_relayed", "unknown"}
MAX_EVIDENCE_BYTES = 25 * 1024 * 1024
SCHEMA_VERSION = 2


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_path(root: Path, run_id: str) -> Path:
    if not ID_PATTERN.fullmatch(run_id):
        raise ValueError("Experiment ID must be lowercase letters, numbers, _ or - (max 64)")
    return root.resolve() / ".aestitch" / "experiments" / (run_id + ".json")


def _store(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _schema_error(detail: str) -> ValueError:
    return ValueError("Experiment schema error: " + detail)


def _validate_packet(data: dict, run_id: str) -> None:
    """Reject wrong field types with a readable error instead of AttributeError."""
    version = data.get("schema_version")
    if version is not None:
        if isinstance(version, bool) or not isinstance(version, int) or version not in (1, 2, SCHEMA_VERSION):
            raise _schema_error("unsupported schema_version in packet: " + run_id)
    review = data.get("user_review")
    if review is not None and not isinstance(review, dict):
        raise _schema_error("user_review must be an object in packet: " + run_id)
    for key in ("evidence", "artifacts"):
        entries = data.get(key)
        if entries is None:
            continue
        if not isinstance(entries, list):
            raise _schema_error(key + " must be an array in packet: " + run_id)
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise _schema_error(f"{key}[{index}] must be an object in packet: {run_id}")
            for field in ("path", "sha256", "class"):
                if field in entry and not isinstance(entry[field], str):
                    raise _schema_error(f"{key}[{index}].{field} must be a string in packet: {run_id}")


def _open(root: Path, run_id: str) -> dict:
    path = _record_path(root, run_id)
    if not path.is_file():
        raise ValueError("Experiment does not exist: " + run_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read experiment packet: " + run_id + ": " + str(exc)) from exc
    if not isinstance(data, dict):
        raise ValueError("Experiment packet must be a JSON object: " + run_id)
    _validate_packet(data, run_id)
    return data


def _verified_file(root: Path, raw: str) -> dict:
    item = Path(raw).expanduser()
    if not item.is_absolute():
        item = root / item
    item = item.resolve()
    if not item.is_file() or not item.is_relative_to(root):
        raise ValueError("Evidence must be an existing file inside experiment root: " + raw)
    if item.stat().st_size > MAX_EVIDENCE_BYTES:
        raise ValueError("Evidence exceeds 25 MB; provide a smaller local evidence file")
    return {
        "path": item.relative_to(root).as_posix(),
        "sha256": sha256(item.read_bytes()).hexdigest(),
        "bytes": item.stat().st_size,
    }


def _normalise_evidence(root: Path, evidence: list) -> list[dict]:
    result = []
    seen: set[tuple[str, str, str]] = set()
    for raw in evidence:
        if isinstance(raw, str):
            path, kind, claim = raw, "unverified", ""
        elif isinstance(raw, dict):
            path = str(raw.get("path", ""))
            kind = str(raw.get("class", "unverified"))
            claim = str(raw.get("claim", ""))
        else:
            raise ValueError("Evidence must be a path or an object with path/class")
        if kind == "user_confirmed":
            raise ValueError("user_confirmed is not recordable by an agent; use "
                             "`aestitch experiment review --user-confirmed` to record user feedback")
        if kind not in RECORDABLE_CLASSES:
            raise ValueError("Invalid evidence class: " + kind)
        item = _verified_file(root, path)
        key = (item["path"], kind, claim.strip())
        if key in seen:
            raise ValueError("Duplicate evidence declaration: " + item["path"] + " (" + kind + ")")
        seen.add(key)
        item.update({"class": kind, "source": "agent", "claim": claim.strip()})
        result.append(item)
    return result


def record_experiment(root: Path, run_id: str, agent: str, model: str,
                      task: str, result: str, artifacts: list[str],
                      skill_version: str = "", comparison: str = "",
                      skill_commit: str = "", evidence: list | None = None) -> dict:
    """Register existing local evidence without copying or uploading it."""
    root = root.resolve()
    path = _record_path(root, run_id)
    if path.exists():
        raise ValueError("Experiment ID already exists; never overwrite evidence")
    if not all(v.strip() for v in (agent, model, task, result)):
        raise ValueError("Agent, model, task and result must be nonempty")
    if skill_commit and not COMMIT_PATTERN.fullmatch(skill_commit):
        raise ValueError("Skill commit must be 7–40 hexadecimal characters")
    if len(artifacts) > 30:
        raise ValueError("Limit experiment artifacts to 30 paths")
    if evidence is not None and artifacts:
        raise ValueError("Use artifacts or evidence, not both")

    if evidence is not None:
        verified_evidence = _normalise_evidence(root, evidence)
        verified = [{k: e[k] for k in ("path", "sha256", "bytes")} for e in verified_evidence]
    else:
        verified = [_verified_file(root, raw) for raw in artifacts]
        verified_evidence = [dict(e, **{"class": "unverified", "source": "agent", "claim": ""})
                             for e in verified]

    item = {
        "schema_version": SCHEMA_VERSION,
        "id": run_id,
        "recorded_at": _stamp(),
        "agent": agent.strip(),
        "model": model.strip(),
        "skill_version": skill_version.strip(),
        "skill_commit": skill_commit.strip(),
        "task": task.strip(),
        "agent_report": result.strip(),
        "comparison": comparison.strip(),
        "artifacts": verified,
        "evidence": verified_evidence,
        "user_review": {"acceptance": "unreviewed", "relative_preference": "unknown",
                        "comment": "", "confirmed": False, "source": "unknown"},
        "interpretation": ("Agent claims are not independently verified. Evidence classes "
                           "describe provenance, not quality. Geometry is not quality."),
    }
    _store(path, item)
    return item


def review_experiment(root: Path, run_id: str, acceptance: str,
                      relative: str, comment: str, user_confirmed: bool,
                      source: str = "unknown", context: str = "") -> dict:
    if not user_confirmed:
        raise ValueError("Only record actual user feedback with --user-confirmed")
    if acceptance not in DECISIONS or acceptance == "unreviewed" or relative not in RELATIVE:
        raise ValueError("Invalid acceptance or relative preference")
    if source not in REVIEW_SOURCES:
        raise ValueError("Review source must be user_direct, agent_relayed or unknown")
    if not comment.strip():
        raise ValueError("Review requires the user's actual feedback in --comment")
    item = _open(root, run_id)
    review = item.get("user_review") or {}
    if review.get("confirmed"):
        raise ValueError("Review already confirmed; preserve history instead of overwriting")
    item["user_review"] = {
        "acceptance": acceptance, "relative_preference": relative,
        "comment": comment.strip(), "confirmed": True, "reviewed_at": _stamp(),
        "source": source, "confirmation_context": context.strip(),
    }
    _store(_record_path(root, run_id), item)
    return item


def _evidence_status(root: Path, entry: dict) -> tuple[str, str]:
    """Return (status, detail) for one evidence entry without reading outside root."""
    raw = entry.get("path")
    if not isinstance(raw, str) or not raw.strip():
        return "invalid_path", "path is missing"
    candidate = Path(raw)
    if candidate.is_absolute():
        return "invalid_path", "absolute path is not allowed"
    resolved = (root.resolve() / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        return "invalid_path", "path resolves outside the experiment root"
    if not resolved.exists():
        return "missing", ""
    if not resolved.is_file():
        return "invalid_path", "path is not a regular file"
    try:
        size = resolved.stat().st_size
        if size > MAX_EVIDENCE_BYTES:
            return "unreadable", "file exceeds 25 MB"
        actual = sha256(resolved.read_bytes()).hexdigest()
    except OSError as exc:
        return "unreadable", str(exc)[:80]
    expected = entry.get("sha256")
    if not isinstance(expected, str) or not expected:
        return "unreadable", "sha256 is not recorded"
    return ("present" if actual == expected else "changed"), ""


def experiment_report(root: Path, run_id: str) -> str:
    item = _open(root, run_id)
    review = item.get("user_review") or {}
    lines = [
        "# Aestitch — experiment evidence packet", "",
        "Experiment: `" + str(item.get("id", run_id)) + "`", "",
        "- Schema: " + str(item.get("schema_version", "legacy/unknown")),
        "- Agent / model: " + str(item.get("agent", "not recorded")) + " / " + str(item.get("model", "not recorded")),
        "- Skill version: " + (str(item.get("skill_version")) if item.get("skill_version") else "not recorded"),
        "- Skill commit (declared): " + (str(item.get("skill_commit")) if item.get("skill_commit") else "not recorded"),
        "- Comparison: " + (str(item.get("comparison")) if item.get("comparison") else "none"),
        "- Recorded: " + str(item.get("recorded_at", "not recorded")), "",
        "## Task", "", str(item.get("task", "not recorded")), "",
        "## Agent-reported outcome (unverified)", "", str(item.get("agent_report", "not recorded")), "",
        "## Local evidence files (not uploaded)", "",
    ]
    evidence = item.get("evidence")
    artifacts = item.get("artifacts") or []
    rows = None
    if evidence:
        rows = [(a, str(a.get("class", "unverified")), True) for a in evidence]
    elif artifacts:
        rows = [(a, "unverified", False) for a in artifacts]
    if rows:
        for entry, kind, modern in rows:
            status, detail = _evidence_status(root.resolve(), entry)
            suffix = (" (" + detail + ")") if detail else ""
            if modern:
                lines.append("- `" + str(entry.get("path", "")) + "` — " + status + suffix +
                             " — class (declared by agent): " + kind +
                             " — sha256: " + str(entry.get("sha256", "unknown")))
            else:
                lines.append("- `" + str(entry.get("path", "")) + "` — " + status + suffix +
                             " — class: unverified (legacy artifact)" +
                             " — sha256: " + str(entry.get("sha256", "unknown")))
    else:
        lines.append("- None attached; visual quality cannot be assessed from agent claims alone")
    source = review.get("source") if isinstance(review.get("source"), str) else "unknown"
    context = review.get("confirmation_context")
    if review.get("confirmed"):
        confirmed_line = "true (source: " + (source or "unknown") + "; not identity verified)"
    else:
        confirmed_line = "false"
    if isinstance(context, str) and context:
        confirmed_line += " — context: " + context
    lines.extend(["", "## User evaluation", "",
                  "- Absolute acceptance: " + str(review.get("acceptance", "unreviewed")),
                  "- Relative preference: " + str(review.get("relative_preference", "unknown")),
                  "- Confirmed: " + confirmed_line,
                  "- Identity verified: no (local CLI records a self-declared action, not authentication)",
                  "- User's words: " + (str(review.get("comment")) if review.get("comment") else "not yet supplied"), "",
                  "## Skill improvement handoff", "",
                  "Separate observed defects, agent explanations, and hypotheses. Review screenshots and interactions before deciding the next Skill change. Do not treat a working prototype as an approved design. Do not promote this packet to personal taste memory.", ""])
    return "\n".join(lines)

"""Local experiment handoff packets: evidence and review, never aesthetic scores."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
DECISIONS = {"unreviewed", "neither", "left", "right", "both", "unsure"}
RELATIVE = {"unknown", "left", "right", "equal"}


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


def _open(root: Path, run_id: str) -> dict:
    path = _record_path(root, run_id)
    if not path.is_file():
        raise ValueError("Experiment does not exist: " + run_id)
    return json.loads(path.read_text(encoding="utf-8"))


def record_experiment(root: Path, run_id: str, agent: str, model: str,
                      task: str, result: str, artifacts: list[str],
                      skill_version: str = "", comparison: str = "") -> dict:
    """Register existing local evidence without copying or uploading it."""
    root = root.resolve()
    path = _record_path(root, run_id)
    if path.exists():
        raise ValueError("Experiment ID already exists; never overwrite evidence")
    if not all(v.strip() for v in (agent, model, task, result)):
        raise ValueError("Agent, model, task and result must be nonempty")
    if len(artifacts) > 30:
        raise ValueError("Limit experiment artifacts to 30 paths")
    verified = []
    for raw in artifacts:
        item = Path(raw).expanduser()
        if not item.is_absolute():
            item = root / item
        item = item.resolve()
        if not item.is_file() or not item.is_relative_to(root):
            raise ValueError("Artifact must be an existing file inside experiment root: " + raw)
        if item.stat().st_size > 25 * 1024 * 1024:
            raise ValueError("Artifact exceeds 25 MB; provide a smaller local evidence file")
        verified.append({
            "path": item.relative_to(root).as_posix(),
            "sha256": sha256(item.read_bytes()).hexdigest(),
            "bytes": item.stat().st_size,
        })
    item = {
        "schema_version": 1, "id": run_id, "recorded_at": _stamp(),
        "agent": agent.strip(), "model": model.strip(),
        "skill_version": skill_version.strip(), "task": task.strip(),
        "agent_report": result.strip(), "comparison": comparison.strip(),
        "artifacts": verified,
        "user_review": {"acceptance": "unreviewed", "relative_preference": "unknown",
                        "comment": "", "confirmed": False},
        "interpretation": "Agent claims are not independently verified. Geometry is not quality.",
    }
    _store(path, item)
    return item


def review_experiment(root: Path, run_id: str, acceptance: str,
                      relative: str, comment: str, user_confirmed: bool) -> dict:
    if not user_confirmed:
        raise ValueError("Only record actual user feedback with --user-confirmed")
    if acceptance not in DECISIONS or acceptance == "unreviewed" or relative not in RELATIVE:
        raise ValueError("Invalid acceptance or relative preference")
    if not comment.strip():
        raise ValueError("Review requires the user's actual feedback in --comment")
    item = _open(root, run_id)
    if item["user_review"].get("confirmed"):
        raise ValueError("Review already confirmed; preserve history instead of overwriting")
    item["user_review"] = {
        "acceptance": acceptance, "relative_preference": relative,
        "comment": comment.strip(), "confirmed": True, "reviewed_at": _stamp(),
    }
    _store(_record_path(root, run_id), item)
    return item


def experiment_report(root: Path, run_id: str) -> str:
    item = _open(root, run_id)
    lines = [
        "# Aestitch — experiment evidence packet", "",
        "Experiment: `" + item["id"] + "`", "",
        "- Agent / model: " + item["agent"] + " / " + item["model"],
        "- Skill version: " + (item["skill_version"] or "not recorded"),
        "- Comparison: " + (item["comparison"] or "none"),
        "- Recorded: " + item["recorded_at"], "",
        "## Task", "", item["task"], "",
        "## Agent-reported outcome (unverified)", "", item["agent_report"], "",
        "## Local evidence files (not uploaded)", "",
    ]
    for a in item["artifacts"]:
        current = root.resolve() / a["path"]
        status = "present" if current.is_file() and sha256(current.read_bytes()).hexdigest() == a["sha256"] else "missing or changed"
        lines.append("- `" + a["path"] + "` — " + status + " — sha256: " + a["sha256"])
    if not item["artifacts"]:
        lines.append("- None attached; visual quality cannot be assessed from agent claims alone")
    review = item["user_review"]
    lines.extend(["", "## User evaluation", "",
                  "- Absolute acceptance: " + review["acceptance"],
                  "- Relative preference: " + review["relative_preference"],
                  "- Confirmed: " + str(review["confirmed"]),
                  "- User's words: " + (review["comment"] or "not yet supplied"), "",
                  "## Skill improvement handoff", "",
                  "Separate observed defects, agent explanations, and hypotheses. Review screenshots and interactions before deciding the next Skill change. Do not treat a working prototype as an approved design. Do not promote this packet to personal taste memory.", ""])
    return "\n".join(lines)

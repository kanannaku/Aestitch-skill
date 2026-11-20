"""Experiment packets preserve local evidence without approval or file duplication."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "aestitch" / "scripts"))
from aestitch_experiments import record_experiment, review_experiment, experiment_report
from aestitch import main


class ExperimentHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "prototypes").mkdir()
        (self.root / "prototypes" / "one.html").write_text("<h1>One</h1>", encoding="utf-8")

    def test_packet_is_unreviewed_and_hash_checks_changes(self):
        p = record_experiment(self.root, "trial-1", "Codex", "GPT", "Two concepts",
                              "Succeeded mechanically", ["prototypes/one.html"], "0.3.0")
        self.assertEqual(p["user_review"]["acceptance"], "unreviewed")
        self.assertFalse(p["user_review"]["confirmed"])
        self.assertEqual(len(p["artifacts"]), 1)
        self.assertIn("present", experiment_report(self.root, "trial-1"))
        (self.root / "prototypes" / "one.html").write_text("changed", encoding="utf-8")
        self.assertIn("changed", experiment_report(self.root, "trial-1"))
        with self.assertRaisesRegex(ValueError, "already exists"):
            record_experiment(self.root, "trial-1", "A", "M", "T", "R", [])

    def test_external_artifact_is_rejected(self):
        outside = Path(__file__).resolve()
        with self.assertRaisesRegex(ValueError, "inside experiment root"):
            record_experiment(self.root, "x", "A", "M", "T", "R", [str(outside)])
        with self.assertRaises(ValueError):
            record_experiment(self.root, "bad/../id", "A", "M", "T", "R", [])

    def test_confirmation_guard_and_immutable_review(self):
        record_experiment(self.root, "trial", "Agent", "Model", "Test", "Output", [])
        with self.assertRaisesRegex(ValueError, "user-confirmed"):
            review_experiment(self.root, "trial", "neither", "right", "Both inadequate", False)
        r = review_experiment(self.root, "trial", "neither", "right", "Both inadequate", True)
        self.assertEqual(r["user_review"]["acceptance"], "neither")
        self.assertEqual(r["user_review"]["relative_preference"], "right")
        self.assertIn("Both inadequate", experiment_report(self.root, "trial"))
        with self.assertRaisesRegex(ValueError, "already confirmed"):
            review_experiment(self.root, "trial", "right", "right", "changed", True)

    def test_evidence_classes_and_skill_commit(self):
        p = record_experiment(
            self.root, "typed", "Claude Code", "DeepSeek", "Check evidence classes",
            "Fixture rendered", [], skill_version="0.3.1", skill_commit="ec83d616",
            evidence=[
                {"path": "prototypes/one.html", "class": "observed", "claim": "Rendered locally"},
                {"path": "prototypes/one.html", "class": "inferred", "claim": "May feel sparse"},
            ])
        self.assertEqual(p["schema_version"], 2)
        self.assertEqual(p["skill_commit"], "ec83d616")
        self.assertEqual([e["class"] for e in p["evidence"]], ["observed", "inferred"])
        report = experiment_report(self.root, "typed")
        self.assertIn("Skill commit (declared): ec83d616", report)
        self.assertIn("class (declared by agent): observed", report)
        self.assertIn("class (declared by agent): inferred", report)
        self.assertNotIn("Identity verified: yes", report)

    def test_skill_commit_is_validated(self):
        with self.assertRaisesRegex(ValueError, "Skill commit"):
            record_experiment(self.root, "bad-commit", "A", "M", "T", "R", [],
                              skill_commit="not-a-commit")

    def test_legacy_packet_missing_new_fields_is_readable(self):
        path = self.root / ".aestitch" / "experiments" / "legacy.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "schema_version": 1,
            "id": "legacy",
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "agent": "legacy-agent",
            "model": "legacy-model",
            "task": "legacy packet",
            "agent_report": "older packet without later fields",
            "user_review": {"acceptance": "unreviewed", "relative_preference": "unknown",
                            "comment": "", "confirmed": False},
        }), encoding="utf-8")
        report = experiment_report(self.root, "legacy")
        self.assertIn("Schema: 1", report)
        self.assertIn("Skill version: not recorded", report)
        self.assertIn("Skill commit (declared): not recorded", report)
        self.assertIn("None attached", report)

    def test_cli_evidence_requires_matching_classes(self):
        self.assertEqual(main(["--root", str(self.root), "experiment", "record",
                               "--id", "pair", "--agent", "A", "--model", "M",
                               "--task", "T", "--result", "R",
                               "--evidence", "prototypes/one.html"]), 2)
        self.assertEqual(main(["--root", str(self.root), "experiment", "record",
                               "--id", "pair", "--agent", "A", "--model", "M",
                               "--task", "T", "--result", "R",
                               "--evidence", "prototypes/one.html",
                               "--evidence-class", "observed"]), 0)
        report = experiment_report(self.root, "pair")
        self.assertIn("class (declared by agent): observed", report)

    def test_cli_record_report(self):
        self.assertEqual(main(["--root", str(self.root), "experiment", "record",
                               "--id", "trial", "--agent", "Claude Code",
                               "--model", "DeepSeek", "--task", "Creative test",
                               "--result", "2 prototypes", "--artifact", "prototypes/one.html"]), 0)
        self.assertEqual(main(["--root", str(self.root), "experiment", "report", "--id", "trial"]), 0)
        self.assertEqual(main(["--root", str(self.root), "experiment", "review", "--id", "trial",
                               "--acceptance", "neither", "--comment", "Neither acceptable"]), 2)


    def test_agent_cannot_record_user_confirmed(self):
        with self.assertRaisesRegex(ValueError, "user_confirmed is not recordable"):
            record_experiment(self.root, "spoof", "Agent", "Model", "T", "R", [],
                              evidence=[{"path": "prototypes/one.html",
                                         "class": "user_confirmed"}])
        self.assertFalse((self.root / ".aestitch" / "experiments" / "spoof.json").exists())
        with self.assertRaises(SystemExit):
            main(["--root", str(self.root), "experiment", "record", "--id", "spoof2",
                  "--agent", "A", "--model", "M", "--task", "T", "--result", "R",
                  "--evidence", "prototypes/one.html",
                  "--evidence-class", "user_confirmed"])
        self.assertFalse((self.root / ".aestitch" / "experiments" / "spoof2.json").exists())

    def test_review_source_is_recorded_honestly(self):
        record_experiment(self.root, "source", "Agent", "Model", "T", "R", [])
        review_experiment(self.root, "source", "neither", "unknown", "Not sure", True)
        report = experiment_report(self.root, "source")
        self.assertIn("source: unknown", report)
        self.assertIn("Identity verified: no", report)
        record_experiment(self.root, "direct", "Agent", "Model", "T", "R", [])
        review_experiment(self.root, "direct", "left", "left", "This one", True,
                          source="user_direct", context="In person")
        report = experiment_report(self.root, "direct")
        self.assertIn("source: user_direct", report)
        self.assertIn("context: In person", report)

    def test_malformed_packet_raises_schema_error(self):
        folder = self.root / ".aestitch" / "experiments"
        folder.mkdir(parents=True, exist_ok=True)
        cases = [
            {"schema_version": "two", "id": "bad"},
            {"user_review": "not-an-object"},
            {"evidence": "not-a-list"},
            {"artifacts": [{"path": 3}]},
        ]
        for index, payload in enumerate(cases):
            payload.setdefault("id", f"bad{index}")
            path = folder / f"bad{index}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "schema error"):
                experiment_report(self.root, f"bad{index}")

    def test_evidence_path_escape_is_invalid_and_not_read(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside, ignore_errors=True))
        secret = outside / "secret.txt"
        secret.write_text("private", encoding="utf-8")
        packet = {
            "schema_version": 2, "id": "escape", "agent": "A", "model": "M",
            "task": "T", "agent_report": "R",
            "user_review": {"confirmed": False},
            "evidence": [
                {"path": "../" + outside.name + "/secret.txt", "sha256": "x", "class": "observed"},
                {"path": str(secret), "sha256": "x", "class": "observed"},
            ],
        }
        folder = self.root / ".aestitch" / "experiments"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "escape.json").write_text(json.dumps(packet), encoding="utf-8")
        report = experiment_report(self.root, "escape")
        self.assertEqual(report.count("invalid_path"), 2)

    def test_missing_and_changed_are_distinct(self):
        record_experiment(self.root, "states", "A", "M", "T", "R",
                          ["prototypes/one.html"])
        (self.root / "prototypes" / "one.html").unlink()
        self.assertIn("missing", experiment_report(self.root, "states"))

    def test_duplicate_evidence_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate evidence"):
            record_experiment(self.root, "dup", "A", "M", "T", "R", [],
                              evidence=[
                                  {"path": "prototypes/one.html", "class": "observed",
                                   "claim": "same"},
                                  {"path": "prototypes/one.html", "class": "observed",
                                   "claim": "same"},
                              ])
        p = record_experiment(self.root, "distinct", "A", "M", "T", "R", [],
                              evidence=[
                                  {"path": "prototypes/one.html", "class": "observed",
                                   "claim": "rendered"},
                                  {"path": "prototypes/one.html", "class": "inferred",
                                   "claim": "may feel sparse"},
                              ])
        self.assertEqual(len(p["evidence"]), 2)

    def test_review_preserves_unknown_fields(self):
        record_experiment(self.root, "ext", "A", "M", "T", "R", [])
        path = self.root / ".aestitch" / "experiments" / "ext.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["future_field"] = {"kept": True}
        path.write_text(json.dumps(data), encoding="utf-8")
        review_experiment(self.root, "ext", "left", "left", "Good", True)
        after = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(after.get("future_field"), {"kept": True})


if __name__ == "__main__":
    unittest.main()

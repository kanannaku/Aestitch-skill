"""Experiment packets preserve local evidence without approval or file duplication."""
from pathlib import Path
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
        self.assertIn("missing or changed", experiment_report(self.root, "trial-1"))
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

    def test_cli_record_report(self):
        self.assertEqual(main(["--root", str(self.root), "experiment", "record",
                               "--id", "trial", "--agent", "Claude Code",
                               "--model", "DeepSeek", "--task", "Creative test",
                               "--result", "2 prototypes", "--artifact", "prototypes/one.html"]), 0)
        self.assertEqual(main(["--root", str(self.root), "experiment", "report", "--id", "trial"]), 0)
        self.assertEqual(main(["--root", str(self.root), "experiment", "review", "--id", "trial",
                               "--acceptance", "neither", "--comment", "Neither acceptable"]), 2)


if __name__ == "__main__":
    unittest.main()

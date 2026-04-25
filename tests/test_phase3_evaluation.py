import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from state_store import StateStore


class Phase3EvaluationTests(unittest.TestCase):
    def test_weak_labels_merge_sqlite_events_queue_and_legacy_feedback(self):
        from evaluation.labels import build_weak_labels

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StateStore(str(root / "state.db"))
            store.record_event("like", "2604.00001v2", {"source": "test"})
            store.record_event("dislike", "2604.00002v1", {"source": "test"})
            store.record_event("ignored", "2604.00005", {"source": "test"})
            store.upsert_queue_item("2604.00002", "Skim Later", note="low positive loses")
            store.upsert_queue_item("2604.00003v3", "Deep Read", note="protected positive")
            store.record_event("dislike", "2604.00003", {"source": "test"})
            store.upsert_queue_item("2604.00004", "Saved", note="protected saved")
            store.record_event("ignore_topic", "2604.00004", {"source": "test"})
            store.upsert_queue_item("2604.00006", "Archived")
            feedback_path = root / "user_feedback.json"
            feedback_path.write_text(
                json.dumps({"liked": ["2604.00007v2"], "disliked": ["2604.00008v1"]}),
                encoding="utf-8",
            )

            labels = build_weak_labels(store, feedback_path=feedback_path)

        self.assertEqual(labels["2604.00001"].label, "relevant")
        self.assertEqual(labels["2604.00001"].weight, 1.0)
        self.assertEqual(labels["2604.00002"].label, "ignored")
        self.assertEqual(labels["2604.00003"].label, "deep_read")
        self.assertEqual(labels["2604.00003"].weight, 2.0)
        self.assertEqual(labels["2604.00004"].label, "saved")
        self.assertEqual(labels["2604.00004"].weight, 1.75)
        self.assertEqual(labels["2604.00005"].label, "ignored")
        self.assertEqual(labels["2604.00006"].label, "neutral")
        self.assertEqual(labels["2604.00007"].label, "relevant")
        self.assertEqual(labels["2604.00008"].label, "ignored")

    def test_metrics_for_ranked_papers_are_deterministic(self):
        from evaluation.labels import WeakLabel
        from evaluation.metrics import evaluate_ranked_papers

        ranked = [
            {"id": "p1"},
            {"id": "p2"},
            {"id": "p3"},
            {"id": "p4"},
        ]
        labels = {
            "p1": WeakLabel("p1", "ignored", -1.0, ["event:dislike"]),
            "p2": WeakLabel("p2", "deep_read", 2.0, ["queue:Deep Read"]),
            "p3": WeakLabel("p3", "relevant", 1.0, ["event:like"]),
            "p4": WeakLabel("p4", "neutral", 0.0, ["queue:Archived"]),
        }

        metrics = evaluate_ranked_papers(ranked, labels, k_values=[2, 4])

        self.assertEqual(metrics["Relevant@2"], 0.5)
        self.assertEqual(metrics["DeepRead@2"], 0.5)
        self.assertEqual(metrics["Ignored@2"], 0.5)
        self.assertEqual(metrics["Relevant@4"], 0.5)
        self.assertEqual(metrics["DeepRead@4"], 0.25)
        self.assertEqual(metrics["Ignored@4"], 0.25)
        self.assertEqual(metrics["MRR"], 0.5)
        expected_ndcg_2 = (2.0 / math.log2(3)) / (2.0 + (1.0 / math.log2(3)))
        self.assertAlmostEqual(metrics["NDCG@2"], expected_ndcg_2, places=6)
        expected_ndcg_4 = ((2.0 / math.log2(3)) + (1.0 / math.log2(4))) / (2.0 + (1.0 / math.log2(3)))
        self.assertAlmostEqual(metrics["NDCG@4"], expected_ndcg_4, places=6)

    def test_dataset_loader_reads_structured_runs_and_history_fallback(self):
        from evaluation.datasets import load_recommendation_runs

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache"
            history_dir = root / "history"
            cache_dir.mkdir()
            history_dir.mkdir()
            (cache_dir / "daily_recommendation.json").write_text(
                json.dumps(
                    {
                        "date": "2026-04-25",
                        "papers": [
                            {"id": "2604.10001v2", "title": "Structured", "score": 5.0}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            runs = load_recommendation_runs(cache_dir=cache_dir, history_dir=history_dir)
            self.assertEqual(runs[0]["date"], "2026-04-25")
            self.assertEqual(runs[0]["papers"][0]["id"], "2604.10001")

            (cache_dir / "daily_recommendation.json").unlink()
            (history_dir / "digest_2026-04-24.md").write_text(
                """
# arXiv Daily Digest

**Research Themes:** conformal prediction

## 1. Historical Paper

**Authors:** Ada Lovelace

**arXiv:** [2604.10002v3](https://arxiv.org/abs/2604.10002v3)

**Summary:** History fallback paper.

**Relevance:** core topic match

**Score:** 4.0
""",
                encoding="utf-8",
            )

            fallback_runs = load_recommendation_runs(cache_dir=cache_dir, history_dir=history_dir)
            self.assertEqual(fallback_runs[0]["date"], "2026-04-24")
            self.assertEqual(fallback_runs[0]["papers"][0]["id"], "2604.10002")

    def test_ablation_variants_return_same_report_shape(self):
        from evaluation.ablation import run_ablation
        from evaluation.labels import WeakLabel

        papers = [
            {
                "id": "p1",
                "title": "Keyword Heavy",
                "abstract": "conformal prediction",
                "score": 1.0,
                "score_details": {"relevance": 4.0, "semantic": 0.0},
            },
            {
                "id": "p2",
                "title": "Semantic Heavy",
                "abstract": "calibrated inference",
                "score": 3.0,
                "score_details": {"relevance": 1.0, "semantic": 5.0},
            },
        ]
        labels = {
            "p1": WeakLabel("p1", "relevant", 1.0, ["event:like"]),
            "p2": WeakLabel("p2", "deep_read", 2.0, ["queue:Deep Read"]),
        }

        report = run_ablation([{"date": "2026-04-25", "papers": papers}], labels, k_values=[1, 2])

        self.assertEqual(
            set(report),
            {"keywords_only", "keywords_semantic", "keywords_semantic_feedback", "full_scorer"},
        )
        for variant in report.values():
            self.assertEqual(variant["run_count"], 1)
            self.assertEqual(variant["paper_count"], 2)
            self.assertIn("Relevant@1", variant["metrics"])
            self.assertIn("NDCG@2", variant["metrics"])

    def test_cli_writes_json_and_markdown_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_dir = root / "cache"
            history_dir = root / "history"
            reports_dir = root / "reports"
            cache_dir.mkdir()
            history_dir.mkdir()
            store = StateStore(str(root / "state.db"))
            store.record_event("like", "2604.20001", {"source": "test"})
            (cache_dir / "daily_recommendation.json").write_text(
                json.dumps(
                    {
                        "date": "2026-04-25",
                        "papers": [{"id": "2604.20001", "title": "Eval Paper", "score": 2.0}],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "evaluation.run_evaluation",
                    "--state-db",
                    str(root / "state.db"),
                    "--cache-dir",
                    str(cache_dir),
                    "--history-dir",
                    str(history_dir),
                    "--output-dir",
                    str(reports_dir),
                    "--k",
                    "1,2",
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            json_reports = sorted(reports_dir.glob("evaluation_*.json"))
            markdown_reports = sorted(reports_dir.glob("evaluation_*.md"))
            self.assertEqual(len(json_reports), 1)
            self.assertEqual(len(markdown_reports), 1)
            payload = json.loads(json_reports[0].read_text(encoding="utf-8"))
            self.assertIn("generated_at", payload)
            self.assertEqual(payload["input_runs"], 1)
            self.assertEqual(payload["k_values"], [1, 2])
            self.assertIn("variants", payload)
            self.assertIn("Evaluation Report", markdown_reports[0].read_text(encoding="utf-8"))

    def test_reports_are_ignored(self):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "reports/evaluation_20260425.json"],
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "reports/evaluation_20260425.json")


if __name__ == "__main__":
    unittest.main()

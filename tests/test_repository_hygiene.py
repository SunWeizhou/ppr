import json
import subprocess
import unittest
from pathlib import Path


class RepositoryHygieneTests(unittest.TestCase):
    def test_user_profile_example_exists_and_matches_config_schema(self):
        profile = Path("user_profile.example.json")

        self.assertTrue(profile.exists())
        data = json.loads(profile.read_text(encoding="utf-8"))
        self.assertEqual(
            set(data),
            {
                "version",
                "keywords",
                "theory_keywords",
                "settings",
                "sources",
                "zotero",
                "venue_priority",
            },
        )
        self.assertIsInstance(data["keywords"], dict)
        self.assertIsInstance(data["theory_keywords"], list)
        self.assertIsInstance(data["settings"], dict)
        self.assertEqual(data["zotero"]["database_path"], "")

    def test_runtime_and_private_files_are_ignored(self):
        paths = [
            "user_profile.json",
            "user_config.json",
            "keywords_config.json",
            "my_scholars.json",
            "cache/paper_cache.json",
            "cache/recommendation_runs/2026-04-23.json",
            "history/digest_2026-04-23.md",
            "daily_arxiv_digest.md",
            "Paper Recommend.zip",
            "reports/evaluation.json",
        ]

        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"],
            input="\n".join(paths) + "\n",
            text=True,
            capture_output=True,
        )

        self.assertEqual(set(result.stdout.splitlines()), set(paths))

    def test_runtime_and_draft_artifacts_are_not_tracked(self):
        result = subprocess.run(
            ["git", "ls-files"],
            text=True,
            capture_output=True,
            check=True,
        )
        tracked = set(result.stdout.splitlines())
        forbidden_exact = {
            "user_profile.json",
            "user_config.json",
            "keywords_config.json",
            "my_scholars.json",
            "daily_arxiv_digest.md",
            "Paper Recommend.zip",
            "progress.txt",
            "prd.json",
        }
        forbidden_prefixes = (
            "Paper Recommend/",
            "scripts/ralph/",
            "cache/recommendation_runs/",
        )
        forbidden = [
            path
            for path in tracked
            if path in forbidden_exact
            or path.startswith(forbidden_prefixes)
            or (path.startswith("cache/") and path.endswith(".json"))
            or (path.startswith("history/digest_") and path.endswith(".md"))
        ]

        self.assertEqual(forbidden, [])

    def test_manifest_includes_runtime_assets_and_excludes_state(self):
        manifest = Path("MANIFEST.in")

        self.assertTrue(manifest.exists())
        text = manifest.read_text(encoding="utf-8")
        self.assertIn("recursive-include templates", text)
        self.assertIn("recursive-include static", text)
        self.assertIn("include user_profile.example.json", text)
        self.assertIn("exclude user_profile.json", text)
        self.assertIn("recursive-exclude cache", text)
        self.assertIn("recursive-exclude history", text)

    def test_ci_runs_explicit_unittest_discovery(self):
        workflow = Path(".github/workflows/tests.yml")

        self.assertTrue(workflow.exists())
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("python -m unittest discover -s tests -v", text)
        self.assertIn("-c constraints.txt", text)

    def test_readme_documents_local_first_setup(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("local-first research triage desk", readme)
        self.assertIn("Inbox / Queue / Library / Monitor / Settings", readme)
        self.assertIn("cp user_profile.example.json user_profile.json", readme)
        self.assertIn("python -m unittest discover -s tests -v", readme)
        self.assertIn("PRD.md", readme)

        for line in readme.splitlines():
            if line.startswith("- `") and "`:" in line:
                path = line.split("`", 2)[1]
                self.assertTrue(Path(path).exists(), path)

    def test_prd_v2_documents_product_constraints(self):
        prd = Path("PRD.md")

        self.assertTrue(prd.exists())
        text = prd.read_text(encoding="utf-8")
        text_lower = text.lower()

        self.assertIn("local-first", text_lower)
        self.assertIn("personalized research triage desk", text_lower)
        self.assertIn("AI Analysis", text)
        self.assertIn("author subscriptions", text)
        self.assertIn("venue subscriptions", text)
        self.assertIn("research question subscriptions", text)
        self.assertIn("require real API keys in tests", text)
        self.assertIn("Monitor is core and must not be deleted", text)
        self.assertIn("Inbox must not expose", text)


if __name__ == "__main__":
    unittest.main()

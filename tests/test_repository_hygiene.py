import json
import subprocess
import unittest
from pathlib import Path

try:
    from packaging.requirements import Requirement
    from packaging.version import Version

    HAS_PACKAGING = True
except ImportError:
    HAS_PACKAGING = False


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
            ".env",
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
        self.assertIn("python -m pytest -q --ignore=tests/visual", text)
        self.assertIn("-c constraints.txt", text)

    def test_readme_documents_local_first_setup(self):
        readme = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("local-first Agent literature research assistant", readme)
        self.assertIn("Inbox / Search / Detail / Reading / Watch / Settings", readme)
        self.assertIn("cp user_profile.example.json user_profile.json", readme)
        self.assertIn("pytest", readme)
        self.assertIn("tests/", readme)

    def test_readme_links_point_to_existing_files(self):
        """Documentation Map entries in README.md must point to real files."""
        readme = Path("README.md").read_text(encoding="utf-8")
        for line in readme.splitlines():
            if line.startswith("- `") and "`:" in line:
                path = line.split("`", 2)[1]
                self.assertTrue(Path(path).exists(), path)

    def test_env_example_documents_deepseek_without_secrets(self):
        example = Path(".env.example")

        self.assertTrue(example.exists())
        text = example.read_text(encoding="utf-8")
        self.assertIn("DEEPSEEK_API_KEY=", text)
        self.assertIn("DEEPSEEK_BASE_URL=https://api.deepseek.com", text)
        self.assertIn("DEEPSEEK_MODEL=deepseek-chat", text)
        self.assertNotIn("sk-", text)

    # ------------------------------------------------------------------ #
    #  Runtime state cleanliness
    # ------------------------------------------------------------------ #

    def test_runtime_cache_does_not_contain_placeholder_titles(self):
        """The runtime cache/app_state.db must not contain obvious placeholder
        titles like 'Stable identity' or 'Test Paper Title'."""
        cache_db = Path("cache/app_state.db")
        if not cache_db.exists():
            self.skipTest("runtime cache not present — cannot inspect")

        import sqlite3
        conn = sqlite3.connect(str(cache_db))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        found_placeholders = []
        for table in tables:
            try:
                for col in ("title", "paper_id", "name"):
                    cursor = conn.execute(
                        f"SELECT DISTINCT {col} FROM \"{table}\" "
                        f"WHERE {col} LIKE '%Stable identity%' "
                        f"OR {col} LIKE '%Test Paper Title%' "
                        f"LIMIT 5"
                    )
                    for row in cursor.fetchall():
                        found_placeholders.append(f"{table}.{col}={row[0]}")
            except (sqlite3.OperationalError, sqlite3.DatabaseError):
                continue
        conn.close()
        self.assertEqual(
            found_placeholders, [],
            f"Placeholder records found in runtime cache: {found_placeholders}"
        )

    # ------------------------------------------------------------------ #
    #  Dependency consistency
    # ------------------------------------------------------------------ #

    def test_constraints_satisfy_requirements_txt(self):
        """Every pinned version in constraints.txt must satisfy the range
        declared in requirements.txt."""
        if not HAS_PACKAGING:
            self.skipTest("packaging library not available")

        constraints = self._parse_constraints()
        requirements = self._parse_requirements("requirements.txt")
        failures = []
        for name, pinned_version in sorted(constraints.items()):
            if name not in requirements:
                continue
            req = requirements[name]
            if pinned_version not in req.specifier:
                failures.append(
                    f"{name}=={pinned_version} does not satisfy "
                    f"requirements.txt specifier {req.specifier}"
                )
        self.assertEqual(failures, [])

    def test_constraints_satisfy_setup_py(self):
        """Every pinned version in constraints.txt must satisfy the range
        declared in setup.py install_requires."""
        if not HAS_PACKAGING:
            self.skipTest("packaging library not available")

        constraints = self._parse_constraints()
        requirements = self._parse_setup_py_requires()
        failures = []
        for name, pinned_version in sorted(constraints.items()):
            if name not in requirements:
                continue
            req = requirements[name]
            if pinned_version not in req.specifier:
                failures.append(
                    f"{name}=={pinned_version} does not satisfy "
                    f"setup.py specifier {req.specifier}"
                )
        self.assertEqual(failures, [])

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_constraints():
        """Return dict {package_name: Version} from constraints.txt."""
        text = Path("constraints.txt").read_text(encoding="utf-8")
        result = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "==" not in line:
                continue
            name, _, version = line.partition("==")
            result[name.strip()] = Version(version.strip())
        return result

    @staticmethod
    def _parse_requirements(path):
        """Return dict {package_name: Requirement} from a pip requirements file."""
        text = Path(path).read_text(encoding="utf-8")
        result = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                req = Requirement(line)
            except Exception:
                continue
            result[req.name] = req
        return result

    @staticmethod
    def _parse_setup_py_requires():
        """Parse install_requires from setup.py by evaluating it safely."""
        import ast

        source = Path("setup.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        reqs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "setup":
                for kw in node.keywords:
                    if kw.arg == "install_requires":
                        reqs = [ast.literal_eval(el) for el in kw.value.elts]
                        break
                break
        result = {}
        for r in reqs:
            try:
                req = Requirement(r)
            except Exception:
                continue
            result[req.name] = req
        return result


if __name__ == "__main__":
    unittest.main()

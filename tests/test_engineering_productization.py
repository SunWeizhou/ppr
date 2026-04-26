import unittest
import tempfile
from pathlib import Path
from unittest import mock


class EngineeringProductizationTests(unittest.TestCase):
    def test_zotero_extractor_uses_sys_platform_for_macos_detection(self):
        from installer.zotero_extractor import ZoteroExtractor

        checked_paths = []

        def fake_exists(path):
            checked_paths.append(path)
            return False

        with mock.patch("sys.platform", "darwin"), mock.patch("os.name", "posix"), mock.patch("os.path.exists", fake_exists):
            ZoteroExtractor().detect_zotero_path()

        self.assertTrue(
            any("Library/Application Support/Zotero" in path for path in checked_paths),
            checked_paths,
        )

    def test_zotero_extractor_resolves_macos_profile_glob(self):
        from installer.zotero_extractor import ZoteroExtractor

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "Library" / "Application Support" / "Zotero" / "Profiles" / "abc" / "zotero.sqlite"
            db_path.parent.mkdir(parents=True)
            db_path.write_text("", encoding="utf-8")

            with mock.patch("sys.platform", "darwin"), mock.patch("os.name", "posix"), mock.patch.dict("os.environ", {"HOME": tmp}):
                detected = ZoteroExtractor().detect_zotero_path()

        self.assertEqual(detected, str(db_path))

    def test_scripts_do_not_hardcode_single_machine_project_root(self):
        script_paths = [
            Path("installer/create_distribution.bat"),
            Path("installer/package.bat"),
            Path("restart_server.bat"),
            Path("run_silent.vbs"),
        ]

        offenders = []
        for path in script_paths:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "D:\\arxiv_recommender" in text or "D:/arxiv_recommender" in text:
                offenders.append(str(path))

        self.assertEqual(offenders, [])

    def test_core_network_clients_do_not_disable_tls_verification(self):
        paths = [
            Path("arxiv_recommender_v5.py"),
            Path("web_server.py"),
            Path("journal_tracker.py"),
            Path("update_journals.py"),
            Path("utils.py"),
            Path("learn_paper.py"),
            Path("fetch_top_journals.py"),
        ]
        offenders = []
        for path in paths:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "CERT_NONE" in text or "check_hostname = False" in text:
                offenders.append(str(path))

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()

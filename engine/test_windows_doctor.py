"""Windows 環境診斷的失敗分類與唯讀契約。"""

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import windows_doctor as doctor


class WindowsDoctorTests(unittest.TestCase):
    def test_new_output_is_accepted_without_creating_it(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as root:
            base = Path(root)
            output = base / "future" / "render"
            checks = []
            doctor._new_output(checks, output)
            self.assertEqual(checks[0]["status"], "ok")
            self.assertFalse(output.exists())
            self.assertFalse(output.parent.exists())
            doctor._new_output(checks, base)
            self.assertEqual(checks[1]["status"], "unavailable")

    def test_missing_dependency_and_wrong_dll_are_distinct(self):
        with patch.object(doctor, "_python_dependency") as dependency, \
             patch.object(doctor, "_native_tools") as native, \
             patch.object(doctor, "_media_tool") as media_tool:
            dependency.side_effect = lambda checks: doctor._record(
                checks, "pyJianYingDraft", "missing", "未安裝")
            native.side_effect = lambda checks: doctor._record(
                checks, "jianying_dll", "mismatch", "SHA-256 不符")
            media_tool.side_effect = lambda checks, name, backend: doctor._record(
                checks, name, "ok", "可用")
            report = doctor.check_environment()
            self.assertEqual(report["status"], "blocked")
            self.assertEqual(report["counts"]["missing"], 1)
            self.assertEqual(report["counts"]["mismatch"], 1)
            with self.assertRaisesRegex(RuntimeError, "pyJianYingDraft.*jianying_dll"):
                doctor.require_environment()

    def test_dependency_api_check_rejects_unpatched_package(self):
        fake_module = SimpleNamespace(__file__=str(Path(__file__)), DraftFolder=type(
            "DraftFolder", (), {"create_draft": lambda self: None}))
        fake_distribution = SimpleNamespace(
            version=doctor.PYJY_VERSION,
            read_text=lambda _: json.dumps({"url": "file:///C:/sample"}))
        checks = []
        with patch.object(doctor.importlib, "import_module", side_effect=[
                fake_module, SimpleNamespace(map_draft_file_paths=lambda *args: None)]), \
             patch.object(doctor.importlib.metadata, "distribution",
                          return_value=fake_distribution):
            doctor._python_dependency(checks)
        self.assertEqual(checks[0]["status"], "mismatch")
        self.assertIn("TextSegment", checks[0]["missing_api"])

    def test_matching_api_still_requires_patched_module_hashes(self):
        exports = {name: object() for name in doctor.PYJY_EXPORTS}
        exports["DraftFolder"] = type("DraftFolder", (), {"create_draft": lambda self: None})
        exports["TextSegment"] = type("TextSegment", (), {"add_keyframe": lambda self: None})
        fake_module = SimpleNamespace(__file__=str(Path(__file__)), **exports)
        fake_distribution = SimpleNamespace(
            version=doctor.PYJY_VERSION,
            read_text=lambda _: json.dumps({"url": "file:///C:/sample"}))
        checks = []
        with patch.object(doctor.importlib, "import_module", side_effect=[
                fake_module, SimpleNamespace(map_draft_file_paths=lambda *args: None)]), \
             patch.object(doctor.importlib.metadata, "distribution",
                          return_value=fake_distribution):
            doctor._python_dependency(checks)
        self.assertEqual(checks[0]["status"], "mismatch")
        self.assertEqual(checks[0]["missing_api"], [])
        self.assertTrue(any(item["actual_sha256"] is None
                            for item in checks[0]["patch_hashes"].values()))

    def test_dll_hash_mismatch_fails_before_native_execution(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as root:
            dll = Path(root) / "videoeditor.dll"
            dll.write_bytes(b"different engine")
            checks = []
            with patch.object(doctor.windows_native_export, "DLL", dll), \
                 patch.object(doctor.windows_native_export, "digest", return_value="0" * 64), \
                 patch.object(doctor.windows_native_export, "msvc_setup",
                              return_value=Path(root) / "vcvars64.bat"):
                doctor._native_tools(checks)
            self.assertEqual(checks[0]["status"], "mismatch")
            self.assertEqual(checks[0]["actual_sha256"], "0" * 64)

    def test_cli_returns_json_and_nonzero_on_failure(self):
        report = {"schema": doctor.SCHEMA, "status": "blocked",
                  "checks": [{"name": "ffmpeg", "status": "missing"}]}
        output = io.StringIO()
        with patch.object(doctor, "check_environment", return_value=report), \
             patch("sys.stdout", output):
            code = doctor.main([])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue()), report)


if __name__ == "__main__":
    unittest.main()

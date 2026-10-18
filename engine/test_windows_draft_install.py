"""Windows 草稿搬移後的素材路徑與非覆寫測試。"""

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
import pyJianYingDraft as jy

from windows_draft_bridge import PlanError, create, file_sha256
from windows_draft_install import install


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source_root = self.root / "source"
        self.target_root = self.root / "target"
        self.source_root.mkdir()
        self.target_root.mkdir()
        photo = self.root / "photo.png"
        Image.new("RGB", (320, 180), "#128080").save(photo)
        self.name = "portable_sample"
        plan = {"schema": "jy14-headless-plan/v1", "name": self.name,
                "canvas": {"width": 320, "height": 180, "fps": 30},
                "tracks": [{"type": "video", "name": "主影片", "segments": [{
                    "source": str(photo), "start_us": 0, "duration_us": 1_000_000,
                    "source_start_us": 0, "source_duration_us": 1_000_000,
                }]}]}
        create(plan, self.source_root, None, None)
        self.source = self.source_root / self.name

    def test_install_rebinds_paths_and_preserves_source(self):
        before = {p.relative_to(self.source): file_sha256(p)
                  for p in self.source.rglob("*") if p.is_file()}
        checked = install(self.source, self.target_root, False)
        self.assertEqual(checked["status"], "validated")
        self.assertFalse((self.target_root / self.name).exists())

        installed = install(self.source, self.target_root, True)
        self.assertEqual(installed["status"], "installed-unverified-in-app")
        destination = self.target_root / self.name
        info = json.loads((destination / "draft_info.json").read_text(encoding="utf-8"))
        meta = json.loads((destination / "draft_meta_info.json").read_text(encoding="utf-8"))
        media_path = Path(info["materials"]["videos"][0]["path"])
        self.assertTrue(media_path.is_relative_to(destination))
        self.assertEqual(file_sha256(media_path), file_sha256(self.source / "materials" / "photo.png"))
        self.assertEqual(meta["draft_materials"][0]["value"][0]["file_Path"], str(media_path))
        self.assertEqual(meta["draft_fold_path"], str(destination))
        self.assertEqual(meta["draft_root_path"], str(self.target_root))
        loaded = jy.DraftFolder(str(self.target_root)).load_template(self.name)
        self.assertEqual(Path(loaded.imported_materials["videos"][0]["path"]), media_path)
        self.assertEqual(before, {p.relative_to(self.source): file_sha256(p)
                                  for p in self.source.rglob("*") if p.is_file()})
        with self.assertRaisesRegex(PlanError, "已存在"):
            install(self.source, self.target_root, True)

    def test_rejects_reference_outside_source(self):
        path = self.source / "draft_info.json"
        info = json.loads(path.read_text(encoding="utf-8"))
        info["materials"]["videos"][0]["path"] = str(self.root / "photo.png")
        path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(PlanError, "未內嵌"):
            install(self.source, self.target_root, False)


if __name__ == "__main__":
    unittest.main()

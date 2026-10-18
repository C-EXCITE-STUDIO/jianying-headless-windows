"""Windows 草稿轉接器的靜態圖片驗證。"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from windows_draft_bridge import PlanError, create, file_sha256, validate


class StillImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "photo.png"
        Image.new("RGB", (640, 360), "#2471a3").save(self.source)
        self.plan = {
            "schema": "jy14-headless-plan/v1",
            "name": "still_test",
            "canvas": {"width": 640, "height": 360, "fps": 30},
            "tracks": [{"type": "video", "name": "主影片", "segments": [{
                "source": str(self.source), "start_us": 0,
                "duration_us": 2_000_000, "source_start_us": 0,
                "source_duration_us": 2_000_000, "speed": 1,
            }]}],
        }

    def test_still_cannot_be_trimmed_or_sped_up(self):
        segment = self.plan["tracks"][0]["segments"][0]
        segment["source_start_us"] = 1
        with self.assertRaisesRegex(PlanError, "靜態圖片"):
            validate(self.plan)
        segment["source_start_us"] = 0
        segment["speed"] = 2
        segment["source_duration_us"] = 4_000_000
        with self.assertRaisesRegex(PlanError, "靜態圖片"):
            validate(self.plan)

    def test_still_is_inlined_and_matches_source(self):
        validate(self.plan)
        fake_app_data = self.root / "fake-local-app-data"
        with patch.dict(os.environ, {"LOCALAPPDATA": str(fake_app_data)}):
            draft_info = create(self.plan, self.root, None, None)
            self.assertEqual(os.environ["LOCALAPPDATA"], str(fake_app_data))
        self.assertFalse(fake_app_data.exists())
        saved = json.loads(draft_info.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["tracks"]), 1)
        self.assertEqual(len(saved["tracks"][0]["segments"]), 1)
        materials = saved["materials"]["videos"]
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["type"], "photo")
        copied = Path(materials[0]["path"])
        self.assertTrue(copied.is_relative_to(draft_info.parent))
        self.assertEqual(file_sha256(copied), file_sha256(self.source))


if __name__ == "__main__":
    unittest.main()

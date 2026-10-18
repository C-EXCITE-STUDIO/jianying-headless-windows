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


class TextMotionTests(unittest.TestCase):
    def setUp(self):
        StillImageTests.setUp(self)
        self.plan["name"] = "text_motion_test"
        self.text = {
            "text": "可編輯動態文字", "start_us": 0, "duration_us": 2_000_000,
            "x": -.25, "y": -.6, "scale": .8, "rotation": -10,
            "opacity": .4,
            "keyframes": {
                "x": [{"at_us": 0, "value": -.25}, {"at_us": 2_000_000, "value": .3}],
                "y": [{"at_us": 0, "value": -.6}, {"at_us": 2_000_000, "value": .4}],
                "scale": [{"at_us": 0, "value": .8}, {"at_us": 2_000_000, "value": 1.5}],
                "rotation": [{"at_us": 0, "value": -10}, {"at_us": 2_000_000, "value": 25}],
            },
        }
        self.plan["tracks"].append({"type": "text", "name": "字幕", "segments": [self.text]})

    def test_static_opacity_and_all_text_motion_channels_are_saved(self):
        validate(self.plan)
        draft_info = create(self.plan, self.root, None, None)
        saved = json.loads(draft_info.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["materials"]["texts"]), 1)
        text_material = saved["materials"]["texts"][0]
        self.assertEqual(json.loads(text_material["content"])["text"], self.text["text"])
        self.assertEqual(text_material["global_alpha"], .4)
        self.assertEqual(json.loads(text_material["content"])["styles"][0]["fill"]["alpha"], 1)
        segment = saved["tracks"][1]["segments"][0]
        self.assertEqual(segment["clip"]["alpha"], 1)
        self.assertEqual(segment["clip"]["transform"], {"x": -.25, "y": -.6})
        self.assertEqual(segment["clip"]["scale"], {"x": .8, "y": .8})
        self.assertEqual(segment["clip"]["rotation"], -10)
        self.assertTrue(segment["uniform_scale"]["on"])
        expected_types = {"x": "KFTypePositionX", "y": "KFTypePositionY",
                          "scale": "KFTypeScaleX", "rotation": "KFTypeRotation"}
        groups = {group["property_type"]: group for group in segment["common_keyframes"]}
        self.assertEqual(set(groups), set(expected_types.values()))
        for channel, property_type in expected_types.items():
            points = groups[property_type]["keyframe_list"]
            self.assertEqual([point["time_offset"] for point in points], [0, 2_000_000])
            self.assertEqual([point["values"][0] for point in points],
                             [point["value"] for point in self.text["keyframes"][channel]])
            self.assertTrue(all(point["curveType"] == "Line" for point in points))

    def test_text_motion_rejects_invalid_channels_times_values_and_conflicts(self):
        import copy

        cases = (
            (lambda text: text["keyframes"].update({"opacity": [
                {"at_us": 0, "value": .4}, {"at_us": 2_000_000, "value": .7}]}), "只支援"),
            (lambda text: text["keyframes"]["x"][1].update(at_us=0), "遞增"),
            (lambda text: text["keyframes"]["x"][0].update(at_us=1), "從 0 開始"),
            (lambda text: text["keyframes"]["y"][1].update(at_us=2_000_001), "片段內"),
            (lambda text: text["keyframes"]["scale"][1].update(value=11), "超出允許範圍"),
            (lambda text: text["keyframes"]["rotation"][1].update(value=float("nan")), "有限數字"),
            (lambda text: text.update(x=0), "不一致"),
            (lambda text: text.update(opacity=1.2), "超出允許範圍"),
        )
        for mutate, error in cases:
            with self.subTest(error=error, mutate=mutate):
                plan = copy.deepcopy(self.plan)
                mutate(plan["tracks"][1]["segments"][0])
                with self.assertRaisesRegex(PlanError, error):
                    validate(plan)


if __name__ == "__main__":
    unittest.main()

"""Windows 已有草稿唯讀檢查與安全副本編輯測試。"""

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from windows_draft_bridge import PlanError, create
from windows_existing_draft import edit_draft, file_snapshot, inspect_draft


class ExistingDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source_root = self.root / "source"
        self.source_root.mkdir()
        photo = self.root / "photo.png"
        Image.new("RGB", (320, 180), "#128080").save(photo)
        plan = {
            "schema": "jy14-headless-plan/v1", "name": "original",
            "canvas": {"width": 320, "height": 180, "fps": 30},
            "tracks": [
                {"type": "video", "name": "畫面", "segments": [{
                    "source": str(photo), "start_us": 0, "duration_us": 2_000_000,
                    "source_start_us": 0, "source_duration_us": 2_000_000,
                }]},
                {"type": "text", "name": "字幕", "segments": [
                    {"text": "第一章", "start_us": 0, "duration_us": 1_000_000},
                    {"text": "第二章", "start_us": 1_000_000, "duration_us": 1_000_000},
                ]},
            ],
        }
        create(plan, self.source_root, None, None)
        self.source = self.source_root / "original"
        self.before = file_snapshot(self.source)
        self.info = json.loads((self.source / "draft_info.json").read_text(encoding="utf-8"))

    def test_inspect_and_edit_precise_segment_without_changing_source(self):
        inspected = inspect_draft(self.source)
        self.assertEqual(inspected["status"], "inspected-read-only")
        self.assertEqual(inspected["file_count"], len(self.before))
        self.assertEqual({row["path"]: row["sha256"] for row in inspected["files"]},
                         {rel.as_posix(): entry["sha256"] for rel, entry in self.before.items()})
        self.assertTrue(all(item["available"] and item["inside_draft"]
                            for item in inspected["material_paths"]))

        video, text = self.info["tracks"]
        first, second = text["segments"]
        target = self.root / "edited"
        operations = [
            {"op": "replace_text", "id": second["id"], "text": "已修改的第二章 😀"},
            {"op": "rename_track", "id": text["id"], "name": "新字幕"},
            {"op": "set_segment", "id": video["segments"][0]["id"],
             "set": {"volume": 0.4, "x": 0.25, "y": -0.15}},
        ]
        dry = edit_draft(self.source, target, operations, False, self.root)
        self.assertEqual(dry["status"], "validated-dry-run")
        self.assertFalse(target.exists())
        self.assertEqual(self.before, file_snapshot(self.source))

        result = edit_draft(self.source, target, operations, True, self.root)
        self.assertEqual(result["status"], "copied-edited-unverified-in-app")
        self.assertTrue(result["source_unchanged"])
        self.assertEqual(self.before, file_snapshot(self.source))
        changed = json.loads((target / "draft_info.json").read_text(encoding="utf-8"))
        meta = json.loads((target / "draft_meta_info.json").read_text(encoding="utf-8"))
        self.assertEqual(changed["id"], meta["draft_id"])
        self.assertNotEqual(changed["id"], self.info["id"])
        self.assertEqual(meta["draft_name"], "edited")
        self.assertEqual(changed["tracks"][1]["name"], "新字幕")
        edited_video = changed["tracks"][0]["segments"][0]
        self.assertEqual(edited_video["volume"], 0.4)
        self.assertEqual(edited_video["clip"]["transform"], {"x": 0.25, "y": -0.15})
        material_by_id = {m["id"]: m for m in changed["materials"]["texts"]}
        first_text = json.loads(material_by_id[first["material_id"]]["content"])
        second_text = json.loads(material_by_id[second["material_id"]]["content"])
        self.assertEqual(first_text["text"], "第一章")
        self.assertEqual(second_text["text"], "已修改的第二章 😀")
        self.assertEqual(second_text["styles"][0]["range"],
                         [0, len("已修改的第二章 😀".encode("utf-16-le")) // 2])
        self.assertTrue(Path(changed["materials"]["videos"][0]["path"]).is_relative_to(target))
        self.assertEqual(self.before[Path("materials/photo.png")]["sha256"],
                         file_snapshot(target)[Path("materials/photo.png")]["sha256"])

    def test_refuses_existing_target_unknown_files_and_effects(self):
        video = self.info["tracks"][0]["segments"][0]
        op = [{"op": "set_segment", "id": video["id"], "set": {"volume": 0.5}}]
        target = self.root / "occupied"
        target.mkdir()
        with self.assertRaisesRegex(PlanError, "已存在"):
            edit_draft(self.source, target, op, True, self.root)
        target.rmdir()

        (self.source / "unknown.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(PlanError, "未知檔案或目錄"):
            edit_draft(self.source, target, op, False, self.root)
        (self.source / "unknown.json").unlink()
        info_path = self.source / "draft_info.json"
        info = json.loads(info_path.read_text(encoding="utf-8"))
        info["materials"]["effects"] = [{"id": "unknown-effect"}]
        info_path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(PlanError, "未知效果"):
            edit_draft(self.source, target, op, False, self.root)
        self.assertFalse(target.exists())

    def test_encrypted_or_unknown_format_is_inspected_but_not_edited(self):
        info_path = self.source / "draft_info.json"
        info_path.write_bytes(b"\x00\x81encrypted")
        (self.source / "draft_content.json").write_bytes(b"\x00\x81encrypted")
        inspected = inspect_draft(self.source)
        self.assertEqual(inspected["draft_info"]["encoding"], "encrypted-or-unsupported")
        self.assertEqual(inspected["timeline_authority"], "unknown-encrypted-ui-mirrors")
        self.assertIn("可能舊於實際時間軸", inspected["warning"])
        video_id = self.info["tracks"][0]["segments"][0]["id"]
        with self.assertRaisesRegex(PlanError, "未知檔案或目錄"):
            edit_draft(self.source, self.root / "encrypted-copy",
                       [{"op": "set_segment", "id": video_id, "set": {"volume": 0.5}}],
                       False, self.root)


if __name__ == "__main__":
    unittest.main()

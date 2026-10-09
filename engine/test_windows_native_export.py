"""Windows 原生匯出的成片契約檢查。"""

import unittest

from .windows_native_export import check_media_contract, draft_contract


class WindowsNativeExportContractTests(unittest.TestCase):
    def setUp(self):
        self.expected = draft_contract({
            "canvas_config": {"width": 1280, "height": 720},
            "fps": 30, "duration": 3_000_000,
            "tracks": [{"type": "video"}, {"type": "audio"}],
        })
        self.media = {"streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1280,
             "height": 720, "avg_frame_rate": "30/1", "nb_read_frames": "90",
             "duration": "3.000000"},
            {"codec_type": "audio", "codec_name": "aac"},
        ]}

    def test_matching_export_passes(self):
        check_media_contract(self.media, self.expected)

    def test_default_portrait_export_is_rejected(self):
        self.media["streams"][0].update(width=1080, height=1920)
        with self.assertRaisesRegex(RuntimeError, "畫布不符"):
            check_media_contract(self.media, self.expected)

    def test_missing_audio_and_short_export_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "缺少音訊"):
            check_media_contract({"streams": self.media["streams"][:1]}, self.expected)
        self.media["streams"][0]["nb_read_frames"] = "89"
        with self.assertRaisesRegex(RuntimeError, "影格數不符"):
            check_media_contract(self.media, self.expected)


if __name__ == "__main__":
    unittest.main()

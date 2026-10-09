# Windows 剪映原生引擎匯出

此實驗入口讀取**現成的** `draft_info.json`，在獨立程序中載入本機剪映 `videoeditor.dll`，還原時間軸並呼叫 `ExportService/exportStart`。輸出由剪映原生引擎產生；FFmpeg 只在完成後檢查媒體與完整解碼。

## 已驗證範圍

- 本機剪映專業版 `11.5.0.14471`，`videoeditor.dll` SHA-256：`37cadef37daff82e2ecdcd65080b9cbd7f6f9436f5e56c1ffb90c52c408eb7fb`。工具只接受這個精確二進位版本。
- 一份 3 秒測試草稿含影片、圖片、文字及音訊。原生輸出已按草稿畫布設定為 1280×720、30 fps、90 幀 H.264 與 AAC，完整解碼通過；抽樣畫面可見草稿內容，音訊非靜音。
- 匯出後核對草稿要求的畫布、影格率、影格數、影像時長及明確音訊軌；不符時停止並保留診斷資料，不把 MP4 標為成功。最初測試曾因引擎預設設定產生 1080×1920，這項檢查及顯式設定已修正該問題。
- 還原完成、`VE_INFO_COMPILE_DONE`、會話關閉及引擎關閉皆留在 `native-helper.log`；輸出與來源雜湊、媒體資訊寫入 `evidence.json`。

這只證明上述版本與樣本的原生無介面匯出路徑可行。其他剪映版本、草稿格式、效果、轉場、關鍵影格、大工程及可配置編碼參數仍須分別驗證。影片解碼與結構檢查不能代替逐鏡畫面及聲音的人工驗收。

## 使用

先安裝 Visual Studio C++ Build Tools，並讓 `ffprobe`、`ffmpeg` 位於 `PATH`。在儲存庫根目錄執行：

```powershell
python engine\windows_native_export.py --draft-info 'D:\Program Files\JianyingPro Drafts\<草稿名稱>\draft_info.json' --out 'D:\原生匯出測試\<新的輸出資料夾>' --timeout 120
```

`--out` 必須是尚未存在的新資料夾。成功後得到 `render.mp4`、`evidence.json`、編譯與引擎日誌。工具不覆寫草稿或既有 MP4，也不讀取帳號資料。來源草稿引用的媒體檔案仍須在原路徑可讀。

本機工作區的 `outputs/windows_dual_workflow.py` 另可用同一份剪輯計畫建立可編輯草稿，並以 `--backend windows-native --write` 匯出 MP4。該整合腳本仍在工作區試驗區，尚未封裝為儲存庫的正式 Skill 命令。使用方式見工作區 `outputs/Windows雙輸出_使用說明.md`。

## 實作邊界

Windows DLL 沒有公開穩定的匯出 SDK。橋接器使用經檢查的 MSVC ABI、精確 DLL 雜湊、這個版本的兩個內部函式位址及匯出設定欄位；剪映更新後必須重新分析和實測，不能沿用位址。官方 `lyra-cli.exe` 在獨立程序中回覆 `unauthorized host process`，本流程沒有更改或繞過它。

原生引擎完成並關閉會話後，供應商執行緒在一般程序退出時可能不結束。橋接器只終止自己的隔離子程序；外層 Python 程序要求引擎完成事件、有效 MP4 及 FFmpeg 完整解碼，才回報成功。

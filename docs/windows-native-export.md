# Windows 剪映原生草稿與 MP4 輸出

Windows 正式入口可從 `jy14-headless-plan/v1` 建立可編輯草稿、複製到本機剪映草稿目錄，並透過已安裝剪映的 `videoeditor.dll` 輸出 H.264/AAC MP4。FFmpeg 在原生輸出後只負責媒體資訊與完整解碼檢查。從頭安裝及建立第一份作品，請依照 [Windows 安裝與快速開始](windows-setup.md)。

## 固定環境與已驗證結果

- 本機已驗證：Windows 11、64 位元 Python 3.13.2、剪映專業版 `11.5.0.14471`。`videoeditor.dll` 的 SHA-256 必須為 `37cadef37daff82e2ecdcd65080b9cbd7f6f9436f5e56c1ffb90c52c408eb7fb`。工具拒絕其他二進位版本。
- 依 [固定依賴安裝](windows-setup.md)重建 pyJianYingDraft 基線與兩個本機修補檔；另需 MSVC C++ Build Tools、`ffmpeg` 和 `ffprobe`。
- 正式 `windows-workflow` 已驗證從新草稿到安裝、原生 MP4 及完整解碼。搬移草稿後重新原生輸出曾取得 90/90 幀；23 軌、154 片段的 30 秒本機案例曾輸出 900/900 幀。
- 文字 X/Y、縮放、旋轉線性關鍵影格與靜態透明度已在六章、12 秒原生成片中作影格量測；360/360 幀完整解碼。同一六章草稿的編輯副本已由使用者確認剪映介面播放、聲音、修改後文字、保存與重開正常。較早的多軌、素材、字體案例亦已通過使用者介面驗收。

已驗證樣本與其他版本、不同素材和更長工程是不同範圍；詳見 [功能對等清單](Windows功能對等清單.md)。

## 命令

以下命令在儲存庫根目錄執行，`$Py` 指向固定依賴虛擬環境中的 `python.exe`。`--out` 和草稿名稱都必須尚未存在；先不加 `--write` 預檢，再用同一命令加上 `--write` 執行。

```powershell
$Py = 'C:\JianyingHeadlessRuntime\.venv\Scripts\python.exe'
$Entry = '.\skills\yichen-jianying-edit\scripts\headless_draft.py'
$DraftRoot = Read-Host '請輸入剪映設定中的草稿根目錄'
& $Py $Entry doctor --draft-root $DraftRoot
& $Py $Entry windows-workflow --plan 'C:\path\to\plan.json' --out 'C:\path\to\new-delivery' --draft-root $DraftRoot --font 'C:\Windows\Fonts\arial.ttf'
& $Py $Entry windows-workflow --plan 'C:\path\to\plan.json' --out 'C:\path\to\new-delivery' --draft-root $DraftRoot --font 'C:\Windows\Fonts\arial.ttf' --write
```

成功後交付目錄包含 `render.mp4`、`workflow_result.json`、工作草稿、原生輸出與驗證證據；剪映草稿目錄中另有可編輯草稿。報告的 `created-unverified-in-app` 表示程式流程完成，仍需在剪映介面檢查內容、保存並重開。

需要把現成的受支援草稿單獨匯出時，使用：

```powershell
& $Py $Entry windows-native-export --draft-info 'C:\path\to\draft\draft_info.json' --out 'C:\path\to\new-export'
```

輸出資料夾包含 `render.mp4`、`evidence.json`、`native-helper.log` 及解碼檢查日誌。工具不覆寫來源草稿與既有輸出。素材必須在草稿引用的路徑可讀。剪映介面保存後，`draft_info.json` 可能不是最新時間軸；遇到含加密側檔的草稿，不應把它直接當作最新版本匯出，先用 `windows-inspect` 唯讀檢查。

## 現有草稿的唯讀檢查與副本編輯

`windows-inspect` 可檢查本機草稿的檔案雜湊、軌道與已知素材引用。若剪映保存後產生 `draft_content.json` 或 `Timelines`，報告會標出加密時間軸的權威性未知；此時 `draft_info.json` 可能不是最新內容。

```powershell
& $Py $Entry windows-inspect --source 'C:\path\to\draft'
```

只對本工具新建、尚未經剪映介面保存、僅含 `draft_info.json`、`draft_meta_info.json` 與 `materials` 的草稿，才可使用 `windows-edit`。先從 `windows-inspect` 結果取出**精確的文字片段 ID**，把操作存成 JSON 陣列，例如：

```json
[{"op":"replace_text","id":"從檢查報告複製的片段 ID","text":"修改後文字"}]
```

```powershell
& $Py $Entry windows-edit --source 'C:\path\to\draft' --target 'C:\work\new-draft-copy' --operations 'C:\work\operations.json' --workspace 'C:\work'
& $Py $Entry windows-edit --source 'C:\path\to\draft' --target 'C:\work\new-draft-copy' --operations 'C:\work\operations.json' --workspace 'C:\work' --write
```

第一行只檢查，第二行才建立新副本。還支援 `rename_track` 和 `set_segment` 對受支援類型的靜態音量／位置修改；未知操作、效果、加密草稿、含關鍵影格片段的靜態修改及既有目標均拒絕。副本建立時核對原件雜湊、重新綁定副本素材路徑並回讀。副本可再用 `windows-native-export --draft-info` 輸出；六章編輯副本已通過介面保存與重開，但其他副本仍須逐份驗收。

## 與 FFmpeg 輸出的區別

`windows-native` 使用本機剪映引擎，需固定 DLL 與可編輯草稿。`windows-ffmpeg` 用獨立渲染器直接從計畫輸出，支援面較小，成片像素與文字字形不保證和原生輸出相同；詳見 [Windows FFmpeg 輸出](windows-ffmpeg.md)。`export --backend windows-native` 與 `windows-native-export` 指向相同原生後端；兩者的輸入都是草稿 `draft_info.json`，不是 FFmpeg 的 `build` 目錄。

## 原生介面邊界

Windows DLL 沒有公開穩定的輸出 SDK。橋接器依賴已檢查的 MSVC ABI、精確 DLL 雜湊、固定版本內部函式位址及輸出設定欄位。剪映更新後應停止並重新分析、驗證。官方 `lyra-cli.exe` 在隔離程序中回覆 `unauthorized host process`；此流程沒有修改或繞過該限制。

供應商執行緒在完成後可能不結束；橋接器只結束自己的隔離子程序。外層 Python 必須看到引擎完成事件、有效 MP4 和 FFmpeg 完整解碼，才回報成功。完整解碼仍需搭配畫面與聲音抽樣；六種幾何蒙版、疊化轉場和輕微抖動目前不列為 Windows 已支援功能。

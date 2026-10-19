# Windows FFmpeg 獨立輸出

此後端從剪輯計畫建立經雜湊綁定的渲染快照，再由 FFmpeg 輸出經完整解碼檢查的 MP4。直接使用 `build`／`export --backend windows-ffmpeg` 時，不需安裝剪映，也不建立剪映可編輯草稿。若需同一計畫的草稿與原生 MP4，請用 [Windows 原生流程](windows-native-export.md)。`windows-workflow --backend windows-ffmpeg` 會另外建立並安裝草稿，但它的 MP4 仍由 FFmpeg 渲染。

## 前置條件

- 直接 `build`／`export` 需要 Python 3.9 或更新；若同時使用 Windows `doctor`／`windows-workflow`，需 64 位元 Python 3.10 或更新。本機完整流程以 3.13.2 驗證。
- `ffmpeg` 和 `ffprobe` 包含 H.264、AAC、overlay、drawtext 支援。
- 計畫含文字時，輸出命令需提供可讀的本機 TTF、OTF 或 TTC 字體；此後端尚不支援每段文字使用不同字體。

工具優先使用命令參數，其次是 `JIANYING_FFMPEG`／`JIANYING_FFPROBE` 環境變數，最後是 PATH。原生剪映後端另有自己的工具檢查，請勿把 FFmpeg 的成功當作原生版本相容證明。

## 建立、核對與輸出

命令中的計畫須把素材路徑換為本機絕對路徑；每個 `--out` 都須指向尚不存在的新目錄。

```powershell
python .\skills\yichen-jianying-edit\scripts\headless_draft.py build --plan 'C:\input\plan.json' --out 'C:\work\windows-build'
python .\skills\yichen-jianying-edit\scripts\headless_draft.py verify-build --build 'C:\work\windows-build'
python .\skills\yichen-jianying-edit\scripts\headless_draft.py export --backend windows-ffmpeg --build 'C:\work\windows-build' --out 'C:\work\windows-export' --font 'C:\Windows\Fonts\arial.ttf'
```

Windows 的 `export` 預設使用此 FFmpeg 後端；建議顯式指定 `--backend windows-ffmpeg`，避免與 `windows-native` 混淆。`build.json` 將計畫、時間軸與每個素材用 SHA-256 綁定；驗證器拒絕不允許的絕對時間軸路徑、上層目錄穿越、符號連結、未知依賴及建立後變動。指定字體另行快照，記錄名稱、大小和雜湊。

此後端支援按序影片、疊加影片、目標時間間隔、切口、固定速度、原音、本機獨立音軌、音量、靜態圖片和基礎文字。音軌及帶音影片可用線性音量關鍵影格；疊加影片可用線性 X/Y 與等比縮放關鍵影格。疊加素材先等比適配畫布，再套用片段縮放，與原生草稿的比例語意一致。帶關鍵影格的來源必須從 0 開始且正常速度播放。

文字位置、縮放、旋轉、透明度關鍵影格，以及每段字體、原生效果、濾鏡、轉場和其他未列的通道均不屬於此 FFmpeg 後端；正式預檢會拒絕。來源裁切與變速後的關鍵影格組合也不支援。單影格 PNG/JPEG 會核對確為一幀，並按計畫時長循環。

成功輸出包含 `render.mp4`、`result.json`、濾鏡圖、FFprobe 證據及 FFmpeg／完整解碼日誌。工具驗證尺寸、影格率、影格數、H.264/yuv420p、時長、來源未變和完整解碼。完整解碼不能取代實際觀看畫面與聽取聲音。

## 程式驗證

```powershell
python .\tools\check_package.py
python -m unittest engine.test_windows_ffmpeg -v
python .\tools\windows_ci_evidence.py
```

GitHub 工作流程只使用一般 `pull_request` 事件與唯讀權限。它依固定的發行資產 ID 下載經審閱的 FFmpeg 壓縮檔，核對精確 SHA-256，並確認 `ffmpeg` 與 `ffprobe` 都來自該壓縮檔且回報固定版本。公開案例使用經審閱、可再分發的素材；私有草稿、帳號資料、系統字體與個人路徑不會上傳。IG 案例也會核對成片的音訊平均音量是否符合指定的 0.5 增益，保留不含路徑的 `audio-gain.json` 報告。

### CI 使用的 FFmpeg 來源

| 項目 | 固定值 |
| --- | --- |
| 版本 | gyan.dev FFmpeg 8.1.2 essentials，靜態 x64、GPLv3（`8.1.2-essentials_build-www.gyan.dev`） |
| 發行頁 | [GyanD/codexffmpeg 8.1.2](https://github.com/GyanD/codexffmpeg/releases/tag/8.1.2)，2026-06-27 發布 |
| 檔案 | `ffmpeg-8.1.2-essentials_build.zip`，資產 ID `459500679`，109,728,040 位元組 |
| SHA-256 | `db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec` |

2026-10-15 的審核確認：下載內容同時符合 GitHub 記錄的摘要與 gyan.dev 公布的校驗值。壓縮檔只有一層頂層目錄，包含 `ffmpeg.exe`、`ffprobe.exe`、`ffplay.exe`、授權、說明、預設設定及 HTML 文件；沒有 DLL、腳本、連結或上層目錄路徑。兩個工具皆為 x64，可用 libx264、libfreetype、libharfbuzz 和 libfribidi；AAC 編碼器已內建。

先前固定的 BtbN 自動建置資產（ID `574819415` 和 `583988006`，後者為 FFmpeg n8.1.3）已由上游移除並回傳 HTTP 404，因此 CI 改用 gyan.dev 的版本化發行檔。如果此資產消失或內容變動，工作流程會停止；須重新審核替代版本並同時更新本表與工作流程，不可取消或放寬摘要檢查。

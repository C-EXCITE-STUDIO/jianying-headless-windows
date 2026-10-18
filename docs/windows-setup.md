# Windows 安裝與快速開始

本頁用一段合成素材完成：**乾淨的依賴目錄 → 環境診斷 → 可編輯草稿 → Windows 剪映原生 MP4**。命令在包含本地 Windows 變更的 `jianying-headless` 儲存庫根目錄執行。這些變更目前仍在本地分支；公開 GitHub 基線未必包含此頁提及的命令。取得另一份檢出時，先確認它含有 `tools/setup_windows.ps1` 與 `engine/windows_dual_workflow.py`。

## 前置條件

| 項目 | 目前已驗證條件 |
| --- | --- |
| 系統 | Windows 11；其他 Windows 版本未完成驗收 |
| Python | 64 位元 3.13.2；`doctor` 最低接受 64 位元 3.10，但其他版本未完成端到端驗收 |
| 剪映 | 專業版 `11.5.0.14471`；`videoeditor.dll` SHA-256 必須為 `37cadef37daff82e2ecdcd65080b9cbd7f6f9436f5e56c1ffb90c52c408eb7fb` |
| 工具 | Git、MSVC C++ Build Tools 的 `vcvars64.bat`、PATH 上可執行的 FFmpeg 與 ffprobe |
| 草稿目錄 | 剪映設定中實際使用的本機草稿根目錄；此工作區為 `D:\Program Files\JianyingPro Drafts` |

剪映應由使用者另外安裝。本儲存庫不含官方程式、DLL、帳號資料或私人素材；`docs/media/` 另有經授權的公開案例衍生件。先用 `python --version`、`git --version`、`ffmpeg -version`、`ffprobe -version` 確認命令可執行。沒有精確剪映版本時，先停在環境診斷，不調低雜湊檢查。

## 1. 安裝固定依賴

在 PowerShell 進入本儲存庫根目錄。`$RuntimeDir` 必須是尚不存在的新路徑；重裝時換新名稱並保留舊目錄供檢查。

```powershell
$RuntimeDir = Join-Path $env:USERPROFILE 'Documents\JianyingHeadlessRuntime'
& .\tools\setup_windows.ps1 -Target $RuntimeDir -PythonExecutable (Get-Command python).Source
$Py = Join-Path $RuntimeDir '.venv\Scripts\python.exe'
$Entry = '.\skills\yichen-jianying-edit\scripts\headless_draft.py'
```

腳本從 `aoguai/pyJianYingDraft` 固定 commit `2b6ed48b0f096e5a76a5b8a68a6d7d233defb463` 取得原始碼，套用 `third_party/pyJianYingDraft/patches/` 內兩個修補檔、核對關鍵原始碼 SHA-256，再安裝 [固定 Python 套件](../requirements-windows.txt)到新虛擬環境。它需要 GitHub 與 Python 套件來源的網路連線；也可透過 `-DependencyRepository` 指向已含固定 commit 的本機 Git 檢出。失敗時保留目標目錄和錯誤資訊，不覆寫舊環境。

## 2. 只讀診斷

```powershell
$DraftRoot = 'D:\Program Files\JianyingPro Drafts'
& $Py $Entry doctor --draft-root $DraftRoot
```

回報 `"status": "ready"` 且所有 `checks` 為 `ok` 才進行下一步。`blocked` 的 `missing`、`mismatch`、`unavailable` 分別表示缺檔、版本不符、檔案或工具無法使用。可加 `--media`、`--font` 逐一檢查檔案，或用 `--out` 檢查一個尚未建立的輸出位置；診斷本身不建立草稿。正式 `windows-workflow` 也會在寫入前跑環境診斷。

## 3. 建立最小計畫

以下使用 FFmpeg 產生三秒合成素材，無需下載第三方媒體；然後從 [最小計畫模板](../examples/windows-minimal.plan.json)填入本機絕對素材路徑和唯一草稿名。

```powershell
$DemoDir = Join-Path $env:USERPROFILE ('Documents\JianyingDemo-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $DemoDir | Out-Null
$Sample = Join-Path $DemoDir 'sample.mp4'
& ffmpeg -n -v error -f lavfi -i 'color=c=0x304060:s=640x360:r=30:d=3' -f lavfi -i 'sine=frequency=440:sample_rate=48000:duration=3' -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest $Sample
$Plan = Get-Content '.\examples\windows-minimal.plan.json' -Raw | ConvertFrom-Json
$Plan.name = 'Windows_Quickstart_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$Plan.tracks[0].segments[0].source = $Sample
$PlanFile = Join-Path $DemoDir 'plan.json'
$Plan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $PlanFile -Encoding utf8
$Font = Join-Path $env:WINDIR 'Fonts\arial.ttf'
& $Py $Entry doctor --draft-root $DraftRoot --media $Sample --font $Font --out (Join-Path $DemoDir 'delivery')
```

若 `ffmpeg` 回報缺少 `libx264`，請換成具有 H.264/AAC 編碼能力的 FFmpeg；若 `arial.ttf` 不存在，改用本機可讀的 TTF、TTC 或 OTF 字體檔。`plan.json` 的 `source` 必須是絕對路徑。合成影片不會修改任何現有素材。

## 4. 預檢、建立草稿並原生輸出

```powershell
$Delivery = Join-Path $DemoDir 'delivery'
& $Py $Entry windows-workflow --plan $PlanFile --out $Delivery --draft-root $DraftRoot --font $Font
& $Py $Entry windows-workflow --plan $PlanFile --out $Delivery --draft-root $DraftRoot --font $Font --write
```

第一行只回報 `validated`，不寫入；第二行才輸出 MP4 並把草稿安裝到 `$DraftRoot`。成功時 `$Delivery\render.mp4`、`$Delivery\workflow_result.json` 和草稿目錄都存在，報告記錄草稿路徑、MP4 SHA-256 及完整解碼結果。輸出名或草稿名已存在時會拒絕覆寫；重新試驗時改用新名稱與新目錄。對新增草稿，先在剪映介面開啟、播放、檢查文字和聲音，保存、退出並重開。

## 失敗恢復與範圍

| 現象 | 處理 |
| --- | --- |
| `doctor` 報 DLL 或版本 `mismatch` | 核對剪映「關於」版本與 DLL 雜湊；不要修改固定值強行通過。 |
| MSVC／FFmpeg／依賴 `missing` | 安裝相應工具後重跑 `doctor`；確認目前 PowerShell 的 PATH。 |
| 素材或字體 `missing` | 核對檔案與絕對路徑，保留原素材。 |
| 目標已存在 | 換新草稿名、新交付目錄或新依賴目錄；不清除舊結果來重試。 |
| 輸出超時、少幀或解碼失敗 | 保留 `job/native-export` 日誌與 `workflow_result.json`，停止使用該 MP4；不關閉影格與完整解碼檢查。 |
| 剪映介面保存後時間軸與 `draft_info.json` 不符 | 使用 `windows-inspect` 唯讀檢查；含加密時間軸側檔的草稿目前不支援自動副本編輯。 |

2026-10-18 已使用乾淨重建的虛擬環境，按本頁合成素材與最小計畫完成 `doctor` 11/11、預檢、草稿建立、原生 3.0 秒 H.264/AAC MP4 的 90/90 幀完整解碼。這是本機可重現結果；尚未證明任意電腦、任意版本或所有原專案效果都相容。原生輸出詳見 [原生說明](windows-native-export.md)，純 FFmpeg 路徑詳見 [FFmpeg 說明](windows-ffmpeg.md)，功能邊界詳見 [Windows 功能對等清單](Windows功能對等清單.md)。

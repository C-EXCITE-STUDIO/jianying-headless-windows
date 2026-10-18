---
name: yichen-jianying-edit
description: 在固定版本的 Windows 或 Apple Silicon macOS 上建立剪映可編輯草稿；按使用者要求產生原生 MP4，或唯讀檢查與安全副本編輯受支援草稿。需另行檢出 Jianying Headless 核心專案。
---

# 剪映無介面剪輯

預設交付可繼續編輯的草稿；使用者要求成片時才執行 MP4 輸出。無介面操作仍需本機安裝匹配版本的剪映。此 Skill 不包含官方程式、DLL、字體、效果或媒體素材。

| 平台 | 已驗證版本 | 命令入口 |
| --- | --- | --- |
| Windows 11 | 剪映專業版 `11.5.0.14471` 與精確 DLL SHA-256；64 位元 Python 3.13.2 | `doctor`、`windows-draft`、`windows-install`、`windows-workflow`、`windows-native-export`、`windows-inspect`、`windows-edit` |
| Apple Silicon macOS | 主版本 11.5.0，相容 11.4.2；精確安裝身分與 codec | `doctor`、`build`、`publish`、`edit`、`export` 等 |

兩平台的介面和可驗收功能不同。Windows 的六類幾何蒙版、疊化轉場、輕微抖動仍未支援；高清黑白濾鏡與橙色描邊花字已移出原專案支援範圍。不要把未知效果靜默刪掉來通過檢查。Windows 已由剪映介面保存的加密草稿可唯讀 `windows-inspect`，目前不能用 `windows-edit` 修改。

## 確認依賴與本次需求

1. 依 [安裝說明](README.md)定位已獲授權的核心專案檢出目錄。同倉時入口自動定位；獨立安裝時設定絕對路徑的 `JIANYING_HEADLESS_ROOT`。不要從其他專案、瀏覽器或聊天中搜集憑據，也不要自動複製官方庫。
2. Windows 先依 [Windows 安裝](../../docs/windows-setup.md)準備固定依賴，執行虛擬環境 Python 的 `headless_draft.py doctor`；macOS 依 [macOS 入門](../../docs/GETTING-STARTED.md)構建 codec 後執行 `doctor`。核心檔、版本或 SHA-256 不符時停止原生操作，不改固定值強行通過。
3. 從本次請求確定素材、新建或修改、速度、音效／BGM 和剪輯力度；不沿用其他項目的速度與刪減偏好。不明確的語義刪減集中詢問。
4. 轉寫是獨立可選依賴。已提供逐詞稿時直接使用；若需付費轉寫，取得本次使用授權，不自動充值、換服務商或重複提交。

## 選擇流程

- Windows 新建及原生輸出：讀 [Windows 安裝與快速開始](../../docs/windows-setup.md)與[原生輸出](../../docs/windows-native-export.md)。`windows-workflow` 預設只做預檢，`--write` 才建立草稿並輸出 MP4；`windows-draft`／`windows-install` 可分步使用。
- Windows 既有草稿：先 `windows-inspect --source`；只有本工具新建、尚未由剪映介面保存的明文 JSON 草稿可用 `windows-edit --source ... --target ... --operations ... --workspace ... [--write]` 建立副本。精確使用片段／軌道 ID；不修改原件。其他格式保持唯讀。
- Windows 不需剪映的成片：讀 [FFmpeg 輸出](../../docs/windows-ffmpeg.md)。其功能與畫面不保證與原生後端一致。
- macOS 新建、修改與原生輸出：分別讀 [無介面計畫](references/headless-macos.md)、[獨立副本編輯](references/edit-existing-macos.md)、[原生輸出](references/export-macos.md)。
- Hypit 工程交接：讀 [素材與字體交接](references/hypit-handoff.md)。口播剪輯讀 [語義與音訊質檢](references/editing-and-qc.md)及[口播計畫格式](references/plan-format.md)。

## 執行與驗收

- 使用獲授權的本機素材；來源保持不動。字幕預設需要，BGM 未提出則不加。不要刪除難以確認的數字、產品名或核心判斷。
- 每次使用新的工作目錄、草稿名稱和輸出目錄。工具核對素材雜湊與目標不覆寫；不要把一致性參數誤作需使用者逐項批准的事項。
- macOS 的 `publish`／`resume-publish` 僅指本機首頁登記，不是線上發布。執行前請使用者保存工作並正常退出剪映，不強制結束其程序。Windows 的 `windows-install` 只處理受支援草稿副本。
- 原生效果只使用本機合法取得的匹配資源，不下載、解鎖或偽造權益；技術輸出成功不等於會員或商業使用許可。
- 草稿須在剪映中檢查畫面、文字、音量和切口，保存、正常退出後冷重開。缺少 UI 驗收時明確標示未完成；導出後檢查實際畫面和聲音，完整解碼不能代替內容驗收。
- 失敗時保留日誌與輸出現場，不自動重試、去掉效果或用舊快照冒充結果。保留原始素材和既有草稿，不自動永久刪除。

## 授權與來源

Skill 與核心專案可分開安裝；只裝 Skill 不含完整後端。原創程式碼授權、剪映協議、素材許可和帳號權益分別適用。詳見[依賴與來源](references/dependencies-and-notices.md)。

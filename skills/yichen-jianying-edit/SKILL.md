---
name: yichen-jianying-edit
description: 在固定版本的 Windows 或 Apple Silicon macOS 上建立剪映可編輯草稿；按使用者要求產生原生 MP4，或唯讀檢查與安全副本編輯受支援草稿。需另行檢出 Jianying Headless 核心專案。
---

# 剪映無介面剪輯

預設交付可繼續編輯的草稿；使用者要求成片時才執行 MP4 輸出。無介面操作仍需本機安裝匹配版本的剪映。此 Skill 不包含官方程式、DLL、字體、效果或媒體素材。

macOS 主版本為 11.5.0，相容 11.4.2；11.6.0 已驗證新建草稿、既有草稿副本編輯及本機字體（含換字體）的保存回讀。11.6.0 的複合片段可離線構建與讀取，但首頁登記與凍結快照交付仍不可用；無介面原生導出會被拒絕，需成片時可使用 `ui-export` 由剪映介面渲染，再由腳本校驗。按安裝版本與指紋選擇設定，不混用導出快照。高清黑白濾鏡與橙色描邊花字已從原專案移除；舊計畫含這些效果時應明確拒絕。

| 平台 | 已驗證版本 | 命令入口 |
| --- | --- | --- |
| Windows 11 | 剪映專業版 `11.5.0.14471` 與精確 DLL SHA-256；64 位元 Python 3.13.2 | `doctor`、`windows-draft`、`windows-install`、`windows-workflow`、`windows-native-export`、`windows-inspect`、`windows-edit` |
| Apple Silicon macOS | 11.5.0、11.4.2；11.6.0 已驗證草稿新建與副本編輯；精確安裝身分與 codec | `doctor`、`build`、`publish`、`edit`、`export`、`ui-export`（按版本支援） |

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
- macOS 新建草稿：讀 [無介面計畫](references/headless-macos.md)，直接建立獨立草稿；線上範本不在發行範圍。修改既有草稿讀 [獨立副本編輯](references/edit-existing-macos.md)，保留原件。
- macOS 成片：讀 [原生輸出](references/export-macos.md)並先檢查 `doctor`。11.5.0／11.4.2 可對已驗證的凍結快照使用無介面 `export`；11.6.0 尚無已審核的無介面導出設定，使用剪映介面渲染及腳本校驗的 `ui-export`，會修改被導出的草稿。
- Hypit 工程交接：讀 [素材與字體交接](references/hypit-handoff.md)，把素材、時間線與字體檔寫入新建計畫；文字片段可用 `font_path` 指定字體。
- 口播剪輯：讀 [語義與音訊質檢](references/editing-and-qc.md)及[口播計畫格式](references/plan-format.md)，由 `scripts/edit_plan.py` 編譯時間映射。若需要音效且未提供本機音訊，計畫可加入英文關鍵詞的 `openverse` 事件；`from-compiled` 後使用 `scripts/openverse_sfx.py add` 選取並寫入獨立音軌，詳見[無介面計畫](references/headless-macos.md)。

## Openverse 音效

- `openverse_sfx.py` 會連線至 Openverse API 與 Freesound 預覽位址；草稿 `build`／`publish` 仍不連網。下載的音效保留各自的 CC0、CC BY 或 CC BY-NC 許可，並不因本專案使用 MIT 而改變。
- 預設優先選 CC0／CC BY，只有缺少合適素材才考慮 CC BY-NC。商單、廣告、帶貨、引流或可營利影片須加 `--commercial`，只選 CC0／CC BY。
- 若關鍵詞找不到合格音效或遇到限流，保留失敗狀態，不刪除使用者要求的音效，也不更換未審核來源。修改計畫關鍵詞後重新編譯，或稍後使用新的 `--work` 重試。
- 交付時轉述本次 `credits.md` 中的許可、CC BY-NC 非商用限制及所需署名文字。選取依據標題、標籤、長度及許可，尚未試聽；在剪映驗收時須一併聆聽。

## 版本限制

11.6.0 的複合片段目前只適用實驗性的離線構建、修改及讀取；首頁登記仍受阻，且無已驗證的複合片段導出路徑。11.5.0 的複合凍結快照曾通過導出驗證，但不代表巢狀草稿已通過保存持久化驗收。

## 執行與驗收

- 使用獲授權的本機素材；來源保持不動。字幕預設需要，BGM 未提出則不加。不要刪除難以確認的數字、產品名或核心判斷。
- 每次使用新的工作目錄、草稿名稱和輸出目錄。工具核對素材雜湊與目標不覆寫；不要把一致性參數誤作需使用者逐項批准的事項。
- macOS 的 `publish`／`resume-publish` 僅指本機首頁登記，不是線上發布。執行前請使用者保存工作並正常退出剪映，不強制結束其程序。Windows 的 `windows-install` 只處理受支援草稿副本。
- 原生效果只使用本機合法取得的匹配資源，不下載、解鎖或偽造權益；技術輸出成功不等於會員或商業使用許可。
- 草稿須在剪映中檢查畫面、文字、音量和切口，保存、正常退出後冷重開。缺少 UI 驗收時明確標示未完成；導出後檢查實際畫面和聲音，完整解碼不能代替內容驗收。
- 失敗時保留日誌與輸出現場，不自動重試、去掉效果或用舊快照冒充結果。保留原始素材和既有草稿，不自動永久刪除。

## 授權與來源

Skill 與核心專案可分開安裝；只裝 Skill 不含完整後端。原創程式碼授權、剪映協議、素材許可和帳號權益分別適用。詳見[依賴與來源](references/dependencies-and-notices.md)。

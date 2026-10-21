# Jianying Headless

面向剪映專業版 macOS 與固定版本 Windows 的本機自動化工具。透過結構化剪輯計畫產生可編輯草稿；支援的版本可由本機剪映引擎無介面輸出 MP4，macOS 11.6.0 則可使用剪映介面匯出並驗證。

本倉庫保留 [mcncarl/jianying-headless](https://github.com/mcncarl/jianying-headless) 的提交歷史與作者署名，並收錄 Windows 版本。兩個平台的支援範圍與驗證條件分別列於下方。

**macOS：主要適配 11.5.0、相容 11.4.2；11.6.0 支援新建與編輯草稿及介面匯出驗證，無介面原生匯出尚未適配。Windows：僅驗證 11.5.0.14471 的精確二進位版本。**

首次使用：Windows 請讀 [Windows 安裝與快速開始](docs/windows-setup.md)，macOS 請讀 [macOS 從零開始](docs/GETTING-STARTED.md)。兩個平台都需匹配精確的本機剪映版本與工具鏈；目前不保證任意電腦安裝即用。

项目适用于 AI 视频工作流的工程交接、批量草稿生成和 Agent 辅助剪辑。
提供 Python 命令行入口及配套 Agent Skill。它不是剪映官方 SDK，运行时需要安装匹配版本的剪映。

## 核心功能

| 功能 | 支持范围 |
| --- | --- |
| 生成可编辑草稿 | 视频分段、多轨组合、变速、音量、画中画、字幕和标题 |
| 导入本地素材 | 视频、PNG、JPEG、GIF、配音、音乐和音效 |
| 本地字體 | macOS 可新建文字或在副本中換字體；Windows 原生流程支援每段指定 TTF／TTC／OTF，副本編輯暫不支援換字體；macOS 詳見[字體說明](docs/LOCAL-FONTS.md) |
| 基礎動畫 | macOS 與 Windows 原生流程支援受驗證通道的線性關鍵影格；Windows FFmpeg 僅支援其文件列出的子集 |
| 原生效果 | macOS：六類靜態幾何蒙版、疊化轉場、輕微抖動；Windows 暫不支援這三項效果 |
| 編輯已有工程 | macOS：多軌草稿副本編輯；Windows：唯讀檢查現有草稿，僅支援本工具新建、尚未經剪映介面保存的草稿作安全副本編輯 |
| 視訊匯出 | macOS 11.5.0／11.4.2 與固定 Windows 11.5.0 可由本機剪映引擎無介面輸出 H.264/AAC MP4；macOS 11.6.0 改用剪映介面匯出與 `ui-export` 驗證 |
| 环境与工程检查 | 核对运行版本、组件身份、素材完整性和草稿保存结果 |

核心流程为：**素材与剪辑计划 → 可编辑剪映草稿 → 原生引擎导出**。
剪映中后续手工修改的内容不会自动同步回原计划或旧导出快照。

## Windows 可編輯草稿與原生 MP4

Windows 本機版已納入正式命令：`doctor`、`windows-draft`、`windows-install`、`windows-workflow`、`windows-native-export`，以及現有草稿的 `windows-inspect`／`windows-edit`。`windows-workflow` 可從同一份計畫建立可編輯草稿並用剪映 `videoeditor.dll` 輸出 H.264/AAC MP4；預設只檢查，`--write` 才實際執行。固定環境為 Windows 11、剪映 `11.5.0.14471`、64 位元 Python 3.13.2，並需精確 DLL SHA-256、MSVC、FFmpeg 與已修補的 pyJianYingDraft。見 [Windows 安裝](docs/windows-setup.md)、[原生輸出](docs/windows-native-export.md)及[功能對等清單](docs/Windows功能對等清單.md)。

功能驗證有不同層級：原生成片完整解碼、畫面抽樣，以及剪映介面中的開啟／保存／重開。六章文字動態草稿的編輯副本已由使用者確認播放、聲音、修改後文字、保存及重開正常；這些證據僅對已測樣本有效。剪映保存後的加密草稿可唯讀檢查，目前不可由 Windows 副本編輯器修改。

## Windows 可選 FFmpeg MP4 輸出

Windows 另提供獨立 FFmpeg 路徑：從剪輯計畫生成已校驗的渲染快照，再輸出 MP4。直接使用 `build`／`export --backend windows-ffmpeg` 時**不需安裝剪映，也不產生可編輯草稿**；支援面小於 Windows 原生路徑。`windows-workflow --backend windows-ffmpeg` 則會另外建立並安裝草稿，但 MP4 仍由 FFmpeg 渲染。
Windows 云端使用本仓库公开 IG 案例验证了完整解码、帧数与音量；
使用方法和限制见 [Windows FFmpeg 导出](docs/windows-ffmpeg.md)。

该独立导出后端由 [@instantgoing](https://github.com/instantgoing) 在 [PR #1](https://github.com/mcncarl/jianying-headless/pull/1) 中贡献。

## macOS 11.6.0 新增路徑

上游新增精確的 macOS 11.6.0 草稿配置、保存回讀規則及本地字體驗收，可建立草稿並編輯已有工程的副本。`export` 無介面原生匯出仍會拒絕此版本；已登記的非複合草稿可由剪映自己的對話框匯出 MP4，再以 `ui-export` 檢查容器、編碼、精確幀數及完整解碼。這條路會開啟並改寫被匯出的草稿，操作與驗證邊界見 [介面匯出說明](docs/UI-EXPORT.md)和[驗證紀錄](docs/VERIFICATION.md)。

可選的 [Openverse 自動音效](skills/yichen-jianying-edit/references/dependencies-and-notices.md)會聯網搜尋 Freesound 預覽並把選定音效加入草稿；音效各自的授權與署名要求仍須核對。11.6.0 的複合片段可離線檢查及構建副本，但尚不能登記首頁或經上述介面路徑交付成片。

## Hypit 协作案例

一个约 **50.23 秒**的 IG 滚动动画教程展示了从 Hypit 到剪映的工程交接。
转换使用原工程的独立画面、配音、图片和文字时间安排，而不是仅导入一条最终成片。

| 工程内容 | 数量 |
| --- | --- |
| 原始素材 | 39 份 |
| 视频与图片 | 8 条轨道、38 个片段 |
| 独立配音 | 1 条轨道、7 个片段 |
| 可编辑文字 | 14 条轨道、109 个片段 |
| 合计 | 23 条轨道、154 个片段 |

该案例已在剪映 11.5.0 完成构建、打开播放、保存、完全退出、冷重开和结构回读，
并通过原生导出的 **1507 / 1507 帧**检查与完整解码检查。

### 画面对照

| Hypit 原成片 | 剪映工程原生导出 |
| --- | --- |
| ![Hypit 原成片六帧](docs/media/hypit-original-frames.png) | ![剪映导出六帧](docs/media/jianying-import-frames.png) |

两组图片均取自真实案例的 1、8、17、28、37、48 秒。展示的是可编辑工程交接，
**不是视觉无损转换**：特殊字体、逐词颜色动画、部分裁切与阴影未原样保留，
第 37 秒的补充画面也存在差异。完整主观视听验收尚未完成。

详见 [Hypit 协作案例](docs/HYPIT-COLLABORATION.md) 和 [媒体说明](docs/media/README.md)。
当前转换是单向、按项目实现；不提供任意 Hypit 工程的一键无损转换或双向同步。

## macOS 執行環境

- Apple Silicon Mac，macOS 26.0+；已验证环境为 macOS 26.5.1。
- 剪映专业版 11.5.0，或兼容配置对应的 11.4.2；11.6.0（官方 build 13281）支持新建草稿（含蒙版、叠化转场、轻微抖动）和编辑已有草稿副本。无界面 `export` 仍拒绝，已登记的非复合草稿可走界面导出与 `ui-export` 验证；复合片段只能离线检查及构建，首页登记仍拒绝。
- Python 3.9+、FFmpeg / ffprobe、Xcode Command Line Tools。
- 已验证桥接工具链：Apple clang 21.0.0 / macOS SDK 26.5。

应用版本、build、官方库哈希、签名与开发者身份均有检查。
未知版本或不匹配组件会被拒绝，不通过放宽校验强行运行。干净机器安装验收尚未完成。
官方引擎、账号数据、原始工程素材库和效果资源不随源码分发。

构建工具选择、安装诊断、登记恢复及字体支持的进展和待验限制见
[Issue 修复进展](docs/ISSUE-REMEDIATION.md)。环境检查通过不等于任意电脑兼容。

## macOS 快速開始

```bash
git clone https://github.com/C-EXCITE-STUDIO/jianying-headless-windows.git
cd jianying-headless-windows
python3 tools/build_native_codec.py
python3 skills/yichen-jianying-edit/scripts/headless_draft.py doctor
```

`doctor` 是**环境检查命令**：检查剪映版本、组件身份和必要工具。
检查通过表示环境符合运行条件，不代表任意草稿都已通过画面、声音或导出验收。

桥接构建只编译项目源码并链接本机已安装程序库，不下载剪映、不修改官方库或账号权益。
编译结果必须匹配固定哈希，否则停止。

按 [计划格式](skills/yichen-jianying-edit/references/headless-macos.md) 准备 JSON，
或参考 [基础计划](examples/basic.plan.json) 和 [Hypit 交接格式示例](examples/hypit-handoff.plan.json)。
示例中的素材路径须替换为有权使用的本地文件。

```bash
python3 skills/yichen-jianying-edit/scripts/headless_draft.py build \
  --plan /absolute/path/to/plan.json --out "$PWD/work/new-build"
python3 skills/yichen-jianying-edit/scripts/headless_draft.py verify-build \
  --build "$PWD/work/new-build"
```

保存当前工作并完全退出剪映后，将新草稿登记到本机首页：

```bash
python3 skills/yichen-jianying-edit/scripts/headless_draft.py publish \
  --build "$PWD/work/new-build" --audit "$PWD/work/new-publish-audit"
```

`publish` 在此仅指本机首页登记，不是互联网发布。生成的草稿仍需实际打开、播放和保存检查。
需要成片时，可独立导出已验证快照：

```bash
python3 skills/yichen-jianying-edit/scripts/headless_draft.py export \
  --build "$PWD/work/new-build" --out "$PWD/work/new-export"
```

输出目录须不存在，成片为该目录下的 `render.mp4`。
导出在隔离进程中运行，默认不联网、不读取账号数据。

## Agent Skill

`skills/yichen-jianying-edit/` 提供 Agent 调用入口、口播计划辅助脚本与操作参考。
Skill 不包含剪映引擎；独立安装后仍需检出核心项目，并指定其路径：

```bash
export JIANYING_HEADLESS_ROOT="/absolute/path/to/jianying-headless-windows"
```

安装说明见 [独立 Skill](skills/yichen-jianying-edit/README.md)。
Skill 另收录于 [yichen-skills](https://github.com/mcncarl/yichen-skills/tree/main/yichen-jianying-edit)。

## 当前限制

- 复合片段仅支持实验性的离线修改与冻结快照导出，尚不能交付为保存可靠的可编辑嵌套草稿。
- 图片/GIF 样本曾出现间歇少一帧；严格帧数检查会拒绝缺帧输出，根因尚未解决。
- 不支持任意剪映版本、任意效果组合、在线模板、资源下载、云端工程或账号权益获取。
- 高清黑白滤镜与橙色描边花字已退出支持范围；含这些效果的计划或旧快照会明确报错。
- 工程结构检查、原生播放、视觉一致性、主观听感与素材许可是不同的验收项目。
- Windows 固定版本的支援狀態另見 [Windows 功能對等清單](docs/Windows功能對等清單.md)；蒙版、疊化及輕微抖動仍未支援，剪映保存後的加密草稿不能由目前的 Windows 編輯命令修改。

详细结果及已知问题见 [验证状态](docs/VERIFICATION.md)。

## 项目结构与验证

| 目录 | 内容 |
| --- | --- |
| `engine/` | 草稿构建、独立副本编辑、资源校验与原生导出 |
| `bridge/` | 文件与管道桥接源码、保留来源声明的接口头文件 |
| `skills/` | Agent Skill 及配套参考 |
| `tools/`、`tests/` | 构建、源码包装检查与可移植测试 |
| `licenses/` | 第三方许可证 |

macOS 可執行完整 `tests/` 離線測試：

```bash
python3 tools/check_package.py
python3 -m unittest discover -s tests -v
```

Windows 請執行套件檢查與 Windows 專屬測試；完整 `tests/` 包含依賴 macOS `fcntl` 的測試：

```powershell
python tools/check_package.py
python -m unittest discover -s tests -p test_package.py -v
python -m unittest discover -s tests -p test_public_media.py -v
python -m unittest engine.test_windows_doctor engine.test_windows_draft_bridge engine.test_windows_draft_install engine.test_windows_existing_draft engine.test_windows_ffmpeg engine.test_windows_native_export -v
```

专项原生测试的本机素材与证据不随仓库分发；源码检查不能替代实际工程验收。

## 许可与来源

本倉庫的原創程式碼採用 [MIT 授權](LICENSE)，保留原作者與貢獻者署名。
第三方內容仍適用各自的授權，例如 pyJianYingDraft 的 Apache-2.0 與 jy-draftc 的 MIT；詳見 [第三方聲明](THIRD_PARTY_NOTICES.md)。
程式碼授權不包含剪映程式與資源、帳號權益、字體或使用者素材的授權。
分发边界见 [分发范围](docs/DISTRIBUTION-SCOPE.md)。

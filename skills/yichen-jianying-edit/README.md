# yichen-jianying-edit

這是 Jianying Headless 的獨立 Agent Skill，包含說明、口播計畫編譯器及固定雜湊的呼叫入口。它不包含剪映引擎，也不把核心源碼複製進 Skill 目錄。現有正式入口支援固定版本 Windows 與 Apple Silicon macOS，平台能力見 [SKILL.md](SKILL.md)。本發行版源自 [mcncarl/jianying-headless](https://github.com/mcncarl/jianying-headless)。

Skill 也收錄於 [yichen-skills](https://github.com/mcncarl/yichen-skills/tree/main/yichen-jianying-edit)；
該外部倉庫的版本依其自身授權，本倉庫的 MIT 授權適用於本倉庫版本。使用時仍需
單獨檢出核心程式碼並安裝匹配版本的剪映。

## 安装

1. 檢出 [C-EXCITE-STUDIO/jianying-headless-windows](https://github.com/C-EXCITE-STUDIO/jianying-headless-windows) 的公開原始碼。
2. Windows 依 [Windows 安裝](../../docs/windows-setup.md)建立固定依賴虛擬環境；macOS 在核心儲存庫執行 `python3 tools/build_native_codec.py`。兩平台接著執行本 Skill 的 `doctor`。
3. 将本目录作为一个完整 Skill 安装到宿主支持的技能目录；不要只复制 `SKILL.md`。
4. Skill 不在核心倉庫內時，設定 `JIANYING_HEADLESS_ROOT=/absolute/path/to/jianying-headless-windows`。

```powershell
# Windows：使用固定依賴虛擬環境中的 python.exe
& 'C:\path\to\runtime\.venv\Scripts\python.exe' 'C:\path\to\yichen-jianying-edit\scripts\headless_draft.py' doctor
```

```bash
# macOS
python3 /absolute/path/to/yichen-jianying-edit/scripts/headless_draft.py doctor
```

路径和环境变量只在用户本机配置，不写入 Git。Skill 会校验核心组件的固定哈希；
源码变更后需要重新验证和同步入口，不能静默接受任意其他版本。

## 运行前提

Windows：目前完整驗證 Windows 11、64 位元 Python 3.13.2、剪映專業版 11.5.0.14471 的精確 DLL 身分、MSVC、FFmpeg／ffprobe 與固定修補依賴。macOS：Apple Silicon、Python 3.9+、FFmpeg／ffprobe、Xcode 編譯工具；11.5.0 為主要無介面導出版本，11.4.2 為相容版本，11.4.0 僅保留歷史草稿配置。11.6.0 已驗證新建、編輯副本及剪映介面導出檢查，無介面原生 `export` 仍拒絕；詳見[介面導出](../../docs/UI-EXPORT.md)。導出快照必須與當前運行版本一致。這些驗證不構成任意電腦或任意剪映版本的相容承諾。

剪辑计划可以直接由用户或 Agent 提供，不强制使用付费 ASR。`asr_once.py` 仅是可选
去重包装器，需要另行提供兼容的转写执行器；`YICHEN_ASR_EXECUTOR` 可以指定它的
本机路径，默认检查当前用户的 `scripts/transcribe.py`。该执行器及任何凭据不随包分发。

自动音效同样是可选步骤：`openverse_sfx.py` 联网访问 Openverse 与 Freesound，挑选的
音效保留各自的 CC 许可，其中 CC BY-NC 禁止商用。不需要时不运行它；草稿 build/publish
不联网。

详细操作见 [SKILL.md](SKILL.md)。本 Skill 不授权自动上传视频、公开草稿、购买资源
或将剪映官方文件重新分发。来源和许可边界见
[dependencies-and-notices.md](references/dependencies-and-notices.md)。

## 许可

原創部分採用 [MIT 授權](LICENSE)。第三方內容保留各自原授權；本 Skill
不授予剪映程式庫、帳號、素材或服務的使用權。來源與相應聲明見
[依賴與來源](references/dependencies-and-notices.md)。

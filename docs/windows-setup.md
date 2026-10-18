# Windows 本機安裝與環境檢查

本流程目前只在 Windows 11、64 位元 Python 3.13.2、剪映專業版
`11.5.0.14471` 上驗證。原生匯出需要該版本的 `videoeditor.dll`，
SHA-256 必須是 `37cadef37daff82e2ecdcd65080b9cbd7f6f9436f5e56c1ffb90c52c408eb7fb`。
另需 Git、MSVC C++ Build Tools 的 `vcvars64.bat`，以及 PATH 上的 FFmpeg 與 ffprobe。

## 安裝固定的 Python 依賴

在專案根目錄用 PowerShell 執行；`-Target` 必須是**尚未存在**的新目錄，
`-PythonExecutable` 指向本機 Python 3.13 的 `python.exe`：

```powershell
& .\tools\setup_windows.ps1 -Target 'C:\JianyingHeadlessRuntime' -PythonExecutable 'C:\Path\To\Python313\python.exe'
```

腳本從 `aoguai/pyJianYingDraft` 的固定基線
`2b6ed48b0f096e5a76a5b8a68a6d7d233defb463` 建立副本，按順序套用
`third_party/pyJianYingDraft/patches/` 的兩個修補檔，核對關鍵原始碼雜湊，
再從 `requirements-windows.txt` 安裝固定版本套件。依賴使用專屬虛擬環境；
失敗時保留目標目錄供檢查，不會覆寫既有環境。

## 診斷

```powershell
& 'C:\JianyingHeadlessRuntime\.venv\Scripts\python.exe' .\skills\yichen-jianying-edit\scripts\headless_draft.py doctor --draft-root 'D:\Program Files\JianyingPro Drafts'
```

命令輸出 JSON。`ready` 表示版本、檔案和工具條件通過；
`blocked` 中的 `missing`、`mismatch`、`unavailable` 分別指缺失、版本不符、
檔案或程式不可用。可加 `--media`、`--font` 檢查指定素材，
或用 `--out` 檢查新輸出位置的上層目錄。診斷不建立或改寫草稿。
建立草稿的正式流程也會在寫入前執行相同環境診斷。

診斷通過僅表示本機先決條件就緒；成片與草稿仍需各自驗證。
這是本機驗證的重裝步驟，跨電腦安裝及其他剪映版本尚未驗收。

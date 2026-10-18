"""只讀檢查 Windows 草稿及原生匯出環境；輸出可供程式判斷的 JSON。"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import struct
import sys
from typing import Any, Iterable

if __package__:
    from . import ffmpeg_tools, windows_native_export
else:
    import ffmpeg_tools
    import windows_native_export


SCHEMA = "jy14-windows-doctor/v1"
PYJY_VERSION = "0.3.0"
PYJY_PATCH_HASHES = {
    "local_materials.py": "b00f71b75996ec9fd8ae03e89e6e6109ae1fda198e07c9a006aab3b7b3ba9476",
    "text_segment.py": "4d54e4e1162cb75c2e3089f224b67c4aa4b024117dbe76fe5d45afff02e42579",
}
PYJY_EXPORTS = (
    "DraftFolder", "TrackSpec", "TrackType", "Timerange", "ClipSettings",
    "VideoSegment", "AudioSegment", "TextSegment", "TextStyle", "TextBorder",
    "KeyframeProperty",
)


def _record(checks: list[dict[str, Any]], name: str, status: str,
            detail: str, **facts: Any) -> None:
    checks.append({"name": name, "status": status, "detail": detail, **facts})


def _file(checks: list[dict[str, Any]], name: str, path: Path) -> None:
    try:
        if path.is_symlink() or not path.is_file():
            _record(checks, name, "missing", "檔案不存在或是符號連結", path=str(path))
            return
        with path.open("rb") as stream:
            stream.read(1)
        _record(checks, name, "ok", "檔案可讀", path=str(path), size=path.stat().st_size)
    except OSError as exc:
        _record(checks, name, "unavailable", f"檔案無法讀取：{exc}", path=str(path))


def _directory(checks: list[dict[str, Any]], name: str, path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        _record(checks, name, "missing", "目錄不存在或是符號連結", path=str(path))
        return
    if not os.access(path, os.R_OK | os.W_OK):
        _record(checks, name, "unavailable", "作業系統回報目錄不可讀寫", path=str(path))
        return
    _record(checks, name, "ok", "目錄存在且作業系統回報可讀寫；未試寫", path=str(path))


def _new_output(checks: list[dict[str, Any]], path: Path) -> None:
    if path.exists() or path.is_symlink():
        _record(checks, "output", "unavailable", "輸出路徑已存在，不會覆寫", path=str(path))
        return
    ancestor = path.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        if ancestor.is_symlink():
            break
        ancestor = ancestor.parent
    if ancestor.is_symlink() or not ancestor.is_dir():
        _record(checks, "output", "missing", "找不到可用的輸出上層目錄", path=str(path))
    elif not os.access(ancestor, os.R_OK | os.W_OK):
        _record(checks, "output", "unavailable", "輸出上層目錄不可讀寫", path=str(path),
                existing_parent=str(ancestor))
    else:
        _record(checks, "output", "ok", "輸出路徑尚未建立；上層目錄可讀寫，未試寫",
                path=str(path), existing_parent=str(ancestor))


def _python_dependency(checks: list[dict[str, Any]]) -> None:
    try:
        module = importlib.import_module("pyJianYingDraft")
        mapping = importlib.import_module("pyJianYingDraft.draft_file_paths")
        distribution = importlib.metadata.distribution("pyJianYingDraft")
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        _record(checks, "pyJianYingDraft", "missing", f"缺少草稿依賴：{exc}")
        return
    except (OSError, ValueError) as exc:
        _record(checks, "pyJianYingDraft", "unavailable", f"無法檢查依賴：{exc}")
        return

    source_path = Path(module.__file__).resolve() if getattr(module, "__file__", None) else None
    source = str(source_path) if source_path else None
    try:
        direct_url = distribution.read_text("direct_url.json")
        origin = json.loads(direct_url) if direct_url else None
    except (OSError, ValueError, json.JSONDecodeError):
        origin = None
    missing = [name for name in PYJY_EXPORTS if not hasattr(module, name)]
    if not callable(getattr(mapping, "map_draft_file_paths", None)):
        missing.append("draft_file_paths.map_draft_file_paths")
    folder_class = getattr(module, "DraftFolder", None)
    text_class = getattr(module, "TextSegment", None)
    if not callable(getattr(folder_class, "create_draft", None)):
        missing.append("DraftFolder.create_draft")
    if not callable(getattr(text_class, "add_keyframe", None)):
        missing.append("TextSegment.add_keyframe")
    patch_hashes: dict[str, dict[str, str | None]] = {}
    read_error = None
    for name, expected in PYJY_PATCH_HASHES.items():
        actual = None
        if source_path is not None:
            try:
                actual = hashlib.sha256((source_path.parent / name).read_bytes()).hexdigest()
            except FileNotFoundError:
                pass
            except OSError as exc:
                read_error = f"無法讀取已安裝模組 {name}：{exc}"
        patch_hashes[name] = {"expected_sha256": expected, "actual_sha256": actual}
    patched = all(item["expected_sha256"] == item["actual_sha256"]
                  for item in patch_hashes.values())
    version = distribution.version
    facts = {"version": version, "expected_version": PYJY_VERSION,
             "source": source, "install_origin": origin, "missing_api": missing,
             "patch_hashes": patch_hashes}
    if read_error:
        _record(checks, "pyJianYingDraft", "unavailable", read_error, **facts)
    elif version != PYJY_VERSION or missing or not patched:
        _record(checks, "pyJianYingDraft", "mismatch", "依賴版本、必要 API 或補丁雜湊不符", **facts)
    elif origin is None:
        _record(checks, "pyJianYingDraft", "mismatch",
                "無法確認安裝來源；請從固定來源安裝", **facts)
    else:
        _record(checks, "pyJianYingDraft", "ok", "版本、安裝來源、必要 API 及補丁雜湊相符", **facts)


def _native_tools(checks: list[dict[str, Any]]) -> None:
    dll = windows_native_export.DLL
    if not dll.is_file() or dll.is_symlink():
        _record(checks, "jianying_dll", "missing", "固定版本的 videoeditor.dll 不存在",
                path=str(dll), expected_version=windows_native_export.DLL_VERSION,
                expected_sha256=windows_native_export.DLL_SHA256)
    else:
        try:
            actual = windows_native_export.digest(dll)
            status = "ok" if actual == windows_native_export.DLL_SHA256 else "mismatch"
            _record(checks, "jianying_dll", status,
                    "剪映 DLL 版本及 SHA-256 相符" if status == "ok" else "剪映 DLL SHA-256 不符",
                    path=str(dll), expected_version=windows_native_export.DLL_VERSION,
                    expected_sha256=windows_native_export.DLL_SHA256, actual_sha256=actual)
        except OSError as exc:
            _record(checks, "jianying_dll", "unavailable", f"無法讀取剪映 DLL：{exc}", path=str(dll))

    try:
        setup = windows_native_export.msvc_setup()
        _record(checks, "msvc", "ok", "找到原生匯出所需的 vcvars64.bat", path=str(setup))
    except (OSError, RuntimeError) as exc:
        _record(checks, "msvc", "missing", str(exc))


def _media_tool(checks: list[dict[str, Any]], name: str, backend: str) -> None:
    try:
        if backend == "windows-native":
            # 原生匯出驗證目前直接使用 PATH；環境變數覆蓋不會傳到該流程。
            raw = shutil.which(name)
            if raw is None:
                raise FileNotFoundError(f"PATH 找不到 {name}")
            path = Path(raw).resolve()
            if not path.is_file() or path.is_symlink():
                raise FileNotFoundError(f"{name} 不是一般執行檔")
        else:
            path = ffmpeg_tools.resolve_tool(name, None, "JIANYING_" + name.upper())
        version = ffmpeg_tools.version(path)
        _record(checks, name, "ok", "工具可執行", path=str(path), version=version)
    except FileNotFoundError as exc:
        _record(checks, name, "missing", str(exc))
    except (OSError, RuntimeError) as exc:
        _record(checks, name, "unavailable", f"工具無法執行：{exc}")


def check_environment(*, draft_root: Path | None = None,
                      media_files: Iterable[Path] = (), font_files: Iterable[Path] = (),
                      output: Path | None = None,
                      backend: str = "windows-native") -> dict[str, Any]:
    """檢查本機條件而不建立檔案；`output` 是預期尚未建立的路徑。"""
    if backend not in {"windows-native", "windows-ffmpeg"}:
        raise ValueError(f"不支援的匯出後端：{backend}")
    checks: list[dict[str, Any]] = []
    _record(checks, "platform", "ok" if sys.platform == "win32" else "mismatch",
            "Windows" if sys.platform == "win32" else "此流程需要 Windows",
            actual=sys.platform, expected="win32")
    py_ok = sys.version_info >= (3, 10) and struct.calcsize("P") == 8
    _record(checks, "python", "ok" if py_ok else "mismatch",
            "64 位元 Python 版本可用" if py_ok else "需要 64 位元 Python 3.10 或更新版本",
            version=sys.version.split()[0], executable=sys.executable,
            bits=struct.calcsize("P") * 8)
    _python_dependency(checks)
    if backend == "windows-native":
        _native_tools(checks)
    for name in ("ffprobe", "ffmpeg"):
        _media_tool(checks, name, backend)
    if draft_root is not None:
        _directory(checks, "draft_root", Path(draft_root))
    if output is not None:
        _new_output(checks, Path(output))
    for index, media in enumerate(media_files):
        _file(checks, f"media[{index}]", Path(media))
    for index, font in enumerate(font_files):
        _file(checks, f"font[{index}]", Path(font))
    counts = {status: sum(item["status"] == status for item in checks)
              for status in ("ok", "missing", "mismatch", "unavailable")}
    return {"schema": SCHEMA, "status": "ready" if counts["ok"] == len(checks) else "blocked",
            "backend": backend, "counts": counts, "checks": checks,
            "read_only": True}


def require_environment(**kwargs: Any) -> dict[str, Any]:
    report = check_environment(**kwargs)
    if report["status"] != "ready":
        failed = "; ".join(f"{item['name']}: {item['detail']}" for item in report["checks"]
                           if item["status"] != "ok")
        raise RuntimeError(f"Windows 環境診斷未通過：{failed}")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("windows-native", "windows-ffmpeg"),
                        default="windows-native")
    parser.add_argument("--draft-root", type=Path)
    parser.add_argument("--out", type=Path, help="預期新建的輸出目錄")
    parser.add_argument("--media", type=Path, action="append", default=[])
    parser.add_argument("--font", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    report = check_environment(draft_root=args.draft_root, output=args.out,
                               media_files=args.media, font_files=args.font,
                               backend=args.backend)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

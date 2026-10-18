"""同一份剪輯計畫在 Windows 產生可編輯剪映草稿與經驗證的 MP4。

預設只驗證；--write 才執行原生匯出並安裝新草稿。
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from windows_draft_bridge import PlanError, create, file_sha256, unique_object, validate
from windows_draft_install import install


import ffmpeg_tools  # noqa: E402
import windows_export  # noqa: E402
import windows_native_export  # noqa: E402
import windows_portable  # noqa: E402
import windows_doctor  # noqa: E402


def read_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8-sig"),
                          object_pairs_hook=unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              PlanError(f"不允許非有限 JSON 數字：{value}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"無法讀取剪輯計畫：{path}") from exc
    validate(plan)
    return plan


def preflight(plan: dict[str, Any], output: Path, draft_root: Path,
              font: Path | None, backend: str = "windows-native") -> dict[str, Any]:
    if sys.platform != "win32":
        raise PlanError("此流程只支援 Windows")
    if output.exists() or output.is_symlink():
        raise PlanError(f"輸出目錄已存在，不覆寫：{output}")
    if not draft_root.is_dir() or draft_root.is_symlink():
        raise PlanError(f"剪映草稿根目錄不存在或是連結：{draft_root}")
    target = draft_root.absolute() / plan["name"]
    if target.exists() or target.is_symlink():
        raise PlanError(f"同名剪映草稿已存在，不覆寫：{target}")
    text_segments = [segment for track in plan["tracks"] if track["type"] == "text"
                     for segment in track["segments"]]
    if text_segments and font is None and any("font" not in segment for segment in text_segments):
        raise PlanError("文字片段缺少 font，請補上每段字體或指定 --font")
    if font is not None and (not font.is_file() or font.is_symlink()):
        raise PlanError(f"字體不存在或是連結：{font}")
    if backend not in {"windows-ffmpeg", "windows-native"}:
        raise PlanError(f"不支援的匯出後端：{backend}")
    if backend == "windows-ffmpeg" and any("font" in segment for segment in text_segments):
        raise PlanError("windows-ffmpeg 暫不支援每段不同字體；請用 windows-native")
    media_files = [Path(segment["source"]) for track in plan["tracks"]
                   if track["type"] in {"video", "audio"}
                   for segment in track["segments"]]
    font_files = [Path(segment["font"]) for segment in text_segments
                  if "font" in segment]
    if font is not None:
        font_files.append(font)
    windows_doctor.require_environment(draft_root=draft_root,
                                       media_files=media_files,
                                       font_files=font_files,
                                       output=output, backend=backend)
    ffprobe = ffmpeg_tools.resolve_tool("ffprobe", None, "JIANYING_FFPROBE")
    # FFmpeg 建置器尚未渲染旋轉／透明度及其關鍵影格。原生草稿由
    # bridge.validate 檢查這些欄位；此副本只用於素材類型與時長預檢。
    probe_plan = deepcopy(plan) if backend == "windows-native" else plan
    if backend == "windows-native":
        for track in probe_plan["tracks"]:
            if track["type"] == "text":
                for segment in track["segments"]:
                    segment.pop("font", None)
            if track["type"] == "video":
                for segment in track["segments"]:
                    segment.pop("rotation", None)
                    segment.pop("opacity", None)
                    if "keyframes" in segment:
                        segment["keyframes"].pop("rotation", None)
                        segment["keyframes"].pop("opacity", None)
                        if not segment["keyframes"]:
                            segment.pop("keyframes")
    assets, duration = windows_portable.validate_plan(probe_plan, ffprobe)
    if backend == "windows-native":
        if (not windows_native_export.DLL.is_file() or
                windows_native_export.digest(windows_native_export.DLL) != windows_native_export.DLL_SHA256):
            raise PlanError("剪映原生 DLL 版本或 SHA-256 不符")
        windows_native_export.msvc_setup()
        ffmpeg_tools.resolve_tool("ffmpeg", None, "JIANYING_FFMPEG")
    return {"name": plan["name"], "duration_us": duration,
            "media_files": len(assets), "draft_target": str(target),
            "output": str(output.absolute()), "backend": backend, "status": "validated"}


def run(plan_path: Path, output: Path, draft_root: Path,
        font: Path | None, write: bool,
        backend: str = "windows-native") -> dict[str, Any]:
    plan = read_plan(plan_path)
    report = preflight(plan, output, draft_root, font, backend)
    if not write:
        return report

    if font is not None:
        font = font.resolve(strict=True)
    plan_hash = file_sha256(plan_path)
    output.mkdir(parents=True, exist_ok=False)
    job = output / "job"
    job.mkdir()
    try:
        stage_root = output / "draft_stage"
        if backend == "windows-ffmpeg":
            build = job / "build"
            windows_portable.build(plan_path.resolve(strict=True), build)
            windows_portable.verify_build(build)
            exported = windows_export.run(build, job / "export", font=font)
            if not exported.get("full_decode_passed") or not exported.get("source_build_unchanged"):
                raise PlanError("MP4 匯出驗證未通過")
            rendered = job / "export" / "render.mp4"
            output_hash = exported["output_sha256"]
        else:
            stage_root.mkdir()
            create(plan, stage_root, None, font)
            draft_info = stage_root / plan["name"] / "draft_info.json"
            draft_hash = file_sha256(draft_info)
            exported = windows_native_export.export(draft_info, job / "native-export")
            if file_sha256(draft_info) != draft_hash:
                raise PlanError("原生匯出期間草稿曾改變")
            rendered = Path(exported["output"])
            output_hash = exported["output_sha256"]
        video_output = output / "render.mp4"
        shutil.copy2(rendered, video_output)
        if file_sha256(video_output) != output_hash:
            raise PlanError("交付 MP4 與匯出結果 SHA-256 不符")

        if backend == "windows-ffmpeg":
            stage_root.mkdir()
            create(plan, stage_root, None, font)
        if file_sha256(plan_path) != plan_hash:
            raise PlanError("執行期間剪輯計畫曾改變")
        installed = install(stage_root / plan["name"], draft_root, True)
        report.update(status="created-unverified-in-app", plan_sha256=plan_hash,
                      mp4=str(video_output), mp4_sha256=file_sha256(video_output),
                      mp4_fully_decoded=True,
                      export_evidence=str(job / ("native-export/evidence.json" if backend == "windows-native"
                                                 else "export/result.json")),
                      draft=installed["target"],
                      draft_info_sha256=installed["draft_info_sha256"],
                      build_job=str(job))
        (output / "workflow_result.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    except Exception as exc:
        (output / "workflow_result.json").write_text(
            json.dumps({**report, "status": "failed", "error": str(exc),
                        "build_job": str(job)}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="新建交付目錄")
    parser.add_argument("--draft-root", type=Path, required=True)
    parser.add_argument("--font", type=Path, help="文字片段未指定 font 時的預設字體")
    parser.add_argument("--backend", choices=("windows-ffmpeg", "windows-native"),
                        default="windows-native", help="MP4 匯出引擎（預設剪映原生）")
    parser.add_argument("--write", action="store_true", help="實際匯出並安裝")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.plan, args.out, args.draft_root, args.font,
                             args.write, args.backend),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, PlanError, ValueError, RuntimeError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

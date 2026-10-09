#!/usr/bin/env python3
"""在 Windows 上以已驗證版本的剪映 videoeditor.dll 匯出現成草稿。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from fractions import Fraction


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "windows_native_export.cpp"
DLL_VERSION = "11.5.0.14471"
DLL_SHA256 = "37cadef37daff82e2ecdcd65080b9cbd7f6f9436f5e56c1ffb90c52c408eb7fb"
# Sandbox-launched tools can virtualize LOCALAPPDATA; the actual per-user
# installation is under the Windows profile's AppData\Local directory.
DLL = Path.home() / "AppData" / "Local" / "JianyingPro" / "Apps" / DLL_VERSION / "videoeditor.dll"


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            state.update(block)
    return state.hexdigest()


def msvc_setup() -> Path:
    root = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    versions = sorted((root / "Microsoft Visual Studio").glob("*/*/VC/Auxiliary/Build/vcvars64.bat"),
                      reverse=True)
    if not versions:
        raise RuntimeError("找不到 MSVC vcvars64.bat；需要 Visual Studio C++ Build Tools")
    return versions[0]


def run_checked(command: list[str], *, cwd: Path, timeout: int, log: Path) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout,
                                check=False)
    except subprocess.TimeoutExpired as error:
        data = error.stderr or b""
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        log.write_text(data[-100_000:], encoding="utf-8")
        raise RuntimeError(f"原生程序逾時；請檢查 {log}") from error
    log.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"程序退出碼 {result.returncode}；請檢查 {log}")
    return result


def build_helper(job: Path) -> Path:
    setup = msvc_setup()
    helper = job / "windows_native_export.exe"
    command = ["cmd.exe", "/d", "/c", "call", str(setup), ">nul", "&&",
               "cl", "/nologo", "/std:c++17", "/EHsc", "/W4",
               "/DUNICODE", "/D_UNICODE", "/Fe:" + str(helper), str(SOURCE)]
    run_checked(command, cwd=job, timeout=120,
                log=job / "compile.log")
    if not helper.is_file():
        raise RuntimeError("MSVC 未產生原生匯出助手")
    return helper


def draft_contract(timeline: dict) -> dict:
    canvas = timeline.get("canvas_config")
    if not isinstance(canvas, dict):
        raise ValueError("草稿缺少畫布設定")
    width, height = canvas.get("width"), canvas.get("height")
    fps, duration = timeline.get("fps"), timeline.get("duration")
    if not all(type(value) is int and value > 0 for value in (width, height, fps, duration)):
        raise ValueError("草稿畫布、影格率或時長無效")
    if width > 8192 or height > 8192 or fps > 120:
        raise ValueError("草稿畫布或影格率超出支援範圍")
    tracks = timeline.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("草稿缺少非空時間軸")
    return {"width": width, "height": height, "fps": fps,
            "duration_us": duration,
            "requires_audio": any(track.get("type") == "audio" for track in tracks
                                  if isinstance(track, dict))}


def check_media_contract(media: dict, expected: dict) -> None:
    streams = media.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(videos) != 1 or videos[0].get("codec_name") != "h264":
        raise RuntimeError("原生 MP4 必須只有一條 H.264 影像流")
    video = videos[0]
    actual_size = (video.get("width"), video.get("height"))
    wanted_size = (expected["width"], expected["height"])
    if actual_size != wanted_size:
        raise RuntimeError(f"原生輸出畫布不符：得到 {actual_size}，草稿要求 {wanted_size}")
    try:
        rate = Fraction(video.get("avg_frame_rate", "0/1"))
        frames = int(video.get("nb_read_frames", 0))
        video_duration = float(video.get("duration", 0))
    except (TypeError, ValueError, ZeroDivisionError) as error:
        raise RuntimeError("原生輸出影格資訊無效") from error
    if rate != expected["fps"]:
        raise RuntimeError(f"原生輸出影格率不符：得到 {rate}，草稿要求 {expected['fps']}")
    target_frames = Fraction(expected["duration_us"] * expected["fps"], 1_000_000)
    minimum, maximum = target_frames.numerator // target_frames.denominator, -(-target_frames.numerator // target_frames.denominator)
    if not minimum <= frames <= maximum:
        raise RuntimeError(f"原生輸出影格數不符：得到 {frames}，草稿要求 {minimum}–{maximum}")
    if abs(video_duration - expected["duration_us"] / 1_000_000) > 1 / expected["fps"] + .05:
        raise RuntimeError("原生輸出影像時長與草稿不符")
    if expected["requires_audio"] and not audios:
        raise RuntimeError("草稿有音訊軌，但原生 MP4 缺少音訊")
    if any(audio.get("codec_name") != "aac" for audio in audios):
        raise RuntimeError("原生輸出音訊不是 AAC")


def validate_mp4(movie: Path, job: Path, timeout: int, expected: dict) -> dict:
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise RuntimeError("需要 ffprobe 與 ffmpeg 驗證原生輸出")
    inspected = run_checked([ffprobe, "-v", "error", "-count_frames", "-show_entries",
                             "format=duration,size,format_name",
                             "-show_entries", "stream=index,codec_type,codec_name,width,height,avg_frame_rate,nb_read_frames,duration",
                             "-of", "json", str(movie)], cwd=job, timeout=30,
                            log=job / "ffprobe.log")
    media = json.loads(inspected.stdout)
    check_media_contract(media, expected)
    run_checked([ffmpeg, "-v", "error", "-xerror", "-i", str(movie), "-f", "null", "NUL"],
                cwd=job, timeout=timeout, log=job / "decode.log")
    return media


def export(draft_info: Path, job: Path, stage_timeout: int = 120) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("此入口僅支援 Windows")
    if not 5 <= stage_timeout <= 43200:
        raise ValueError("每階段逾時須介於 5 至 43200 秒")
    if draft_info.is_symlink():
        raise ValueError("草稿 JSON 不可為符號連結")
    draft_info = draft_info.resolve(strict=True)
    if not draft_info.is_file():
        raise ValueError("需要一般草稿 JSON 檔案")
    input_hash = digest(draft_info)
    timeline = json.loads(draft_info.read_text(encoding="utf-8-sig"))
    if not isinstance(timeline, dict):
        raise ValueError("草稿缺少非空時間軸")
    expected = draft_contract(timeline)
    if not DLL.is_file() or digest(DLL) != DLL_SHA256:
        raise RuntimeError("剪映原生 DLL 版本或 SHA-256 不符；停止使用固定 ABI")
    job = job.absolute()
    if job.exists() or job.is_symlink() or not job.parent.is_dir():
        raise ValueError("--out 必須是現有父資料夾中的新資料夾")
    job.mkdir()
    helper = build_helper(job)
    movie = job / "render.mp4"
    result = run_checked([str(helper), str(DLL), str(draft_info), str(movie), str(stage_timeout),
                          str(expected["width"]), str(expected["height"]), str(expected["fps"])],
                         cwd=job, timeout=stage_timeout * 2 + 45,
                         log=job / "native-helper.log")
    if "stage=restore_done result=1" not in result.stderr or \
            "compile_done=1" not in result.stderr or \
            "stage=completed_process_exit" not in result.stderr or \
            not movie.is_file():
        raise RuntimeError("缺少草稿還原或原生編譯完成證據")
    media = validate_mp4(movie, job, stage_timeout * 2 + 45, expected)
    if digest(draft_info) != input_hash:
        raise RuntimeError("原生匯出期間來源草稿曾改變")
    evidence = {
        "schema": "jy14-windows-native-export/v1",
        "status": "native-export-encoded-and-decoded",
        "engine": "Jianying videoeditor.dll ExportService",
        "engine_version": DLL_VERSION,
        "engine_sha256": DLL_SHA256,
        "adapter_source_sha256": digest(SOURCE),
        "input_draft": str(draft_info),
        "input_sha256": input_hash,
        "draft_contract": expected,
        "output": str(movie),
        "output_sha256": digest(movie),
        "media": media,
    }
    (job / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-info", type=Path, required=True, help="現成草稿的 draft_info.json")
    parser.add_argument("--out", type=Path, required=True, help="新的輸出資料夾")
    parser.add_argument("--timeout", type=int, default=120, help="還原及匯出各階段的秒數上限")
    args = parser.parse_args()
    try:
        result = export(args.draft_info, args.out, args.timeout)
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as error:
        print(f"原生匯出失敗：{error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "output": result["output"],
                      "evidence": str(Path(result["output"]).parent / "evidence.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

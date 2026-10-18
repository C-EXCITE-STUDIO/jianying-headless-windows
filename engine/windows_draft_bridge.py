"""將 Jianying Headless 的基本計畫轉為 Windows 剪映可編輯草稿（試驗版）。

依賴 aoguai/pyJianYingDraft 的 DraftFolder API。預設只驗證計畫；--write 才建立草稿。
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional


SCHEMA = "jy14-headless-plan/v1"
STILL_EXTENSIONS = {".png", ".jpg", ".jpeg"}
VIDEO_KEYS = {
    "source", "start_us", "duration_us", "source_start_us", "source_duration_us",
    "speed", "volume", "scale", "x", "y", "rotation", "opacity", "keyframes",
}
AUDIO_KEYS = {
    "source", "start_us", "duration_us", "source_start_us", "source_duration_us",
    "speed", "volume", "keyframes",
}
TEXT_KEYS = {
    "text", "start_us", "duration_us", "size", "x", "y", "scale", "rotation",
    "color", "border_color", "border_width", "font",
}
INVALID_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class PlanError(ValueError):
    pass


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PlanError(f"JSON 欄位重複：{key}")
        result[key] = value
    return result


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def registration_scope(user_data: Optional[Path]):
    """只有明確提供 User Data 時，才允許依賴庫更新首頁索引。"""
    if user_data is not None:
        yield
        return
    previous = os.environ.pop("LOCALAPPDATA", None)
    try:
        yield
    finally:
        if previous is not None:
            os.environ["LOCALAPPDATA"] = previous


def check_keys(value: dict[str, Any], allowed: set[str], where: str) -> None:
    extra = set(value) - allowed
    if extra:
        raise PlanError(f"{where} 含尚未支援的欄位：{', '.join(sorted(extra))}")


def number(value: Any, where: str, low: Optional[float] = None,
           high: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PlanError(f"{where} 必須是有限數字")
    result = float(value)
    if low is not None and result < low or high is not None and result > high:
        raise PlanError(f"{where} 超出允許範圍")
    return result


def micros(value: Any, where: str, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0):
        raise PlanError(f"{where} 必須是{'正' if positive else '非負'}整數微秒")
    return value


def color(value: Any, where: str) -> tuple[float, float, float]:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise PlanError(f"{where} 必須是 #RRGGBB")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def clean_name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        raise PlanError(f"{where} 必須是非空名稱")
    if INVALID_NAME.search(value) or value.endswith((" ", ".")):
        raise PlanError(f"{where} 含 Windows 路徑不允許的字元")
    if value.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *
                                         (f"COM{i}" for i in range(1, 10)), *
                                         (f"LPT{i}" for i in range(1, 10))}:
        raise PlanError(f"{where} 是 Windows 保留名稱")
    return value


def validate_keyframes(seg: dict[str, Any], where: str, length: int,
                       source_start: int, speed: float, kind: str) -> None:
    if "keyframes" not in seg:
        return
    series = seg["keyframes"]
    allowed = {"volume"} if kind == "audio" else {"volume", "x", "y", "scale", "rotation", "opacity"}
    if not isinstance(series, dict) or not series or set(series) - allowed:
        raise PlanError(f"{where}.keyframes 目前只支援 {', '.join(sorted(allowed))}")
    if source_start != 0 or speed != 1:
        raise PlanError(f"{where} 關鍵影格暫不支援來源裁切或變速")
    for channel, points in series.items():
        if not isinstance(points, list) or len(points) < 2:
            raise PlanError(f"{where}.keyframes.{channel} 至少需要兩個點")
        previous = -1
        for index, point in enumerate(points):
            loc = f"{where}.keyframes.{channel}[{index}]"
            if not isinstance(point, dict) or set(point) != {"at_us", "value"}:
                raise PlanError(f"{loc} 必須只有 at_us 與 value")
            at = micros(point["at_us"], f"{loc}.at_us")
            if at <= previous or at > length:
                raise PlanError(f"{loc}.at_us 必須遞增且在片段內")
            previous = at
            low, high = ((0, 4) if channel == "volume" else
                         (.01, 10) if channel == "scale" else
                         (0, 1) if channel == "opacity" else
                         (-360, 360) if channel == "rotation" else (-5, 5))
            number(point["value"], f"{loc}.value", low, high)
        if points[0]["at_us"] != 0:
            raise PlanError(f"{where} 第一個 {channel} 關鍵影格必須從 0 開始")
        if channel in seg and abs(points[0]["value"] - seg[channel]) > 1e-7:
            raise PlanError(f"{where}.{channel} 與第一個關鍵影格不一致")


def validate(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise PlanError("計畫根節點必須是物件")
    check_keys(plan, {"schema", "name", "canvas", "tracks"}, "計畫")
    if plan.get("schema") != SCHEMA:
        raise PlanError(f"僅支援 {SCHEMA}")
    name = clean_name(plan.get("name"), "草稿名稱")
    if len(name.encode("utf-8")) >= 200:
        raise PlanError("草稿名稱過長")
    canvas = plan.get("canvas")
    if not isinstance(canvas, dict):
        raise PlanError("canvas 必須是物件")
    check_keys(canvas, {"width", "height", "fps"}, "canvas")
    for field in ("width", "height", "fps"):
        micros(canvas.get(field), f"canvas.{field}", positive=True)
    if not (16 <= canvas["width"] <= 8192 and 16 <= canvas["height"] <= 8192):
        raise PlanError("canvas 寬高必須在 16..8192 之間")
    if canvas["fps"] not in {24, 25, 30, 50, 60}:
        raise PlanError("不支援的影格率")
    tracks = plan.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise PlanError("tracks 必須是非空陣列")
    names: set[str] = set()
    duration = 0
    media: set[str] = set()
    fonts: set[str] = set()
    for ti, track in enumerate(tracks):
        where = f"tracks[{ti}]"
        if not isinstance(track, dict):
            raise PlanError(f"{where} 必須是物件")
        check_keys(track, {"type", "name", "segments"}, where)
        kind = track.get("type")
        if kind not in {"video", "audio", "text"} or (ti == 0 and kind != "video"):
            raise PlanError(f"{where} 類型錯誤；第一軌必須為主影片")
        track_name = clean_name(track.get("name"), f"{where}.name")
        if track_name in names:
            raise PlanError(f"軌道名稱重複：{track_name}")
        names.add(track_name)
        segments = track.get("segments")
        if not isinstance(segments, list) or (ti == 0 and not segments):
            raise PlanError(f"{where}.segments 必須是陣列，主影片軌不可空")
        last_end = 0
        for si, seg in enumerate(segments):
            loc = f"{where}.segments[{si}]"
            if not isinstance(seg, dict):
                raise PlanError(f"{loc} 必須是物件")
            check_keys(seg, {"video": VIDEO_KEYS, "audio": AUDIO_KEYS,
                             "text": TEXT_KEYS}[kind], loc)
            start = micros(seg.get("start_us", 0), f"{loc}.start_us")
            length = micros(seg.get("duration_us"), f"{loc}.duration_us", positive=True)
            if start < last_end or (ti == 0 and start != last_end):
                raise PlanError(f"{loc} 重疊，或主影片軌有空隙")
            last_end = start + length
            if ti == 0:
                duration = last_end
            elif last_end > duration:
                raise PlanError(f"{loc} 超出主影片長度")
            if kind in {"video", "audio"}:
                source = seg.get("source")
                if not isinstance(source, str) or not Path(source).is_absolute():
                    raise PlanError(f"{loc}.source 必須是絕對路徑")
                path = Path(source)
                if not path.is_file() or path.is_symlink():
                    raise PlanError(f"素材不存在或是符號連結：{path}")
                media.add(str(path.resolve()))
                source_start = micros(seg.get("source_start_us", 0), f"{loc}.source_start_us")
                speed = number(seg.get("speed", 1), f"{loc}.speed", .1, 8)
                source_length = micros(seg.get("source_duration_us", length),
                                       f"{loc}.source_duration_us", positive=True)
                if kind == "video" and path.suffix.lower() in STILL_EXTENSIONS:
                    if source_start != 0 or speed != 1:
                        raise PlanError(f"{loc} 靜態圖片不支援來源裁切或變速")
                if abs(source_length / speed - length) > 2:
                    raise PlanError(f"{loc} 來源時長、速度及目標時長不一致")
                number(seg.get("volume", 1), f"{loc}.volume", 0, 4)
                validate_keyframes(seg, loc, length, source_start, speed, kind)
                if kind == "video":
                    number(seg.get("scale", 1), f"{loc}.scale", .01)
                    number(seg.get("opacity", 1), f"{loc}.opacity", 0, 1)
                    for key in ("x", "y", "rotation"):
                        number(seg.get(key, 0), f"{loc}.{key}")
            else:
                if not isinstance(seg.get("text"), str):
                    raise PlanError(f"{loc}.text 必須是文字")
                if "font" in seg:
                    font_path = seg["font"]
                    if not isinstance(font_path, str) or not Path(font_path).is_absolute():
                        raise PlanError(f"{loc}.font 必須是絕對路徑")
                    path = Path(font_path)
                    if path.suffix.lower() not in {".ttf", ".ttc", ".otf"} or not path.is_file() or path.is_symlink():
                        raise PlanError(f"字體不存在、格式不支援或是符號連結：{path}")
                    fonts.add(str(path.resolve()))
                number(seg.get("size", 6), f"{loc}.size", 1, 100)
                for key in ("x", "y", "rotation"):
                    number(seg.get(key, 0), f"{loc}.{key}")
                number(seg.get("scale", 1), f"{loc}.scale", .01)
                color(seg.get("color", "#FFFFFF"), f"{loc}.color")
                if "border_color" in seg:
                    color(seg["border_color"], f"{loc}.border_color")
                number(seg.get("border_width", .05), f"{loc}.border_width", 0, .2)
    return {"name": name, "duration_us": duration, "tracks": len(tracks),
            "segments": sum(len(t["segments"]) for t in tracks),
            "media": sorted(media), "fonts": sorted(fonts)}


def create(plan: dict[str, Any], root: Path, user_data: Optional[Path],
           font: Optional[Path]) -> Path:
    if sys.platform != "win32":
        raise PlanError("草稿寫入只在 Windows 執行")
    if not root.is_dir():
        raise PlanError(f"草稿根目錄不存在：{root}")
    if user_data is not None and not user_data.is_dir():
        raise PlanError(f"User Data 目錄不存在：{user_data}")
    if font is not None and (not font.is_file() or font.is_symlink()):
        raise PlanError(f"字體不存在：{font}")
    output = root / plan["name"]
    if output.exists() or output.is_symlink():
        raise PlanError(f"草稿已存在，不覆寫：{output}")
    validation = validate(plan)
    source_hashes = {source: file_sha256(Path(source)) for source in validation["media"]}
    font_sources = set(validation["fonts"])
    if font is not None:
        font_sources.add(str(font.resolve(strict=True)))
    font_hashes = {source: file_sha256(Path(source)) for source in font_sources}

    try:
        import pyJianYingDraft as jy
    except ImportError as exc:
        raise PlanError("缺少 pyJianYingDraft，請安裝相容版本") from exc

    folder = jy.DraftFolder(str(root), user_data_path=str(user_data) if user_data else None)
    c = plan["canvas"]
    script = folder.create_draft(plan["name"], c["width"], c["height"], c["fps"],
                                 maintrack_adsorb=False, allow_replace=False)
    for track in plan["tracks"]:
        kind = track["type"]
        name = track["name"]
        script.append_track(jy.TrackSpec(getattr(jy.TrackType, kind), name))
        for item in track["segments"]:
            target = jy.Timerange(item.get("start_us", 0), item["duration_us"])
            if kind in {"video", "audio"}:
                speed = item.get("speed", 1)
                source_length = item.get("source_duration_us", item["duration_us"])
                source = jy.Timerange(item.get("source_start_us", 0), source_length)
                keyframes = item.get("keyframes", {})
                points = keyframes.get("volume")
                first_volume = points[0]["value"] if points else item.get("volume", 1)
                kwargs = {"source_timerange": source, "volume": first_volume}
                if kind == "video":
                    scale = (keyframes["scale"][0]["value"] if "scale" in keyframes
                             else item.get("scale", 1))
                    first_x = keyframes["x"][0]["value"] if "x" in keyframes else item.get("x", 0)
                    first_y = keyframes["y"][0]["value"] if "y" in keyframes else item.get("y", 0)
                    kwargs["clip_settings"] = jy.ClipSettings(
                        alpha=(keyframes["opacity"][0]["value"] if "opacity" in keyframes
                               else item.get("opacity", 1)),
                        rotation=(keyframes["rotation"][0]["value"] if "rotation" in keyframes
                                  else item.get("rotation", 0)),
                        scale_x=scale, scale_y=scale, transform_x=first_x,
                        transform_y=first_y)
                    segment = jy.VideoSegment(item["source"], target, **kwargs)
                else:
                    segment = jy.AudioSegment(item["source"], target, **kwargs)
                for channel, series in keyframes.items():
                    for point in series:
                        if kind == "audio":
                            segment.add_keyframe(point["at_us"], point["value"])
                        else:
                            prop = {"volume": jy.KeyframeProperty.volume,
                                    "x": jy.KeyframeProperty.position_x,
                                    "y": jy.KeyframeProperty.position_y,
                                    "scale": jy.KeyframeProperty.uniform_scale,
                                    "rotation": jy.KeyframeProperty.rotation,
                                    "opacity": jy.KeyframeProperty.alpha}[channel]
                            segment.add_keyframe(prop, point["at_us"], point["value"])
            else:
                scale = item.get("scale", 1)
                border = None
                if item.get("border_width", .05) > 0:
                    border = jy.TextBorder(
                        color=color(item.get("border_color", "#000000"), "border_color"),
                        width=item.get("border_width", .05) / .2 * 100)
                segment = jy.TextSegment(
                    item["text"], target,
                    font_path=item.get("font", str(font) if font else None),
                    style=jy.TextStyle(size=item.get("size", 6),
                                       color=color(item.get("color", "#FFFFFF"), "color")),
                    clip_settings=jy.ClipSettings(
                        rotation=item.get("rotation", 0), scale_x=scale, scale_y=scale,
                        transform_x=item.get("x", 0), transform_y=item.get("y", -.78)),
                    border=border)
            script.add_segment(segment, name)
    with registration_scope(user_data):
        script.save(inline_materials=True)
    result = output / "draft_info.json"
    if not result.is_file() or result.stat().st_size == 0:
        raise PlanError(f"草稿保存後缺少有效主檔：{result}")
    saved = json.loads(result.read_text(encoding="utf-8"))
    if len(saved.get("tracks", [])) != len(plan["tracks"]):
        raise PlanError("保存後軌道數量不符")
    copied_hashes: set[str] = set()
    for bucket in ("videos", "audios", "images"):
        for material in saved.get("materials", {}).get(bucket, []):
            path = Path(material["path"])
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(output.resolve()):
                raise PlanError(f"保存後素材未指向草稿副本：{path}")
            copied_hashes.add(file_sha256(path))
    if not set(source_hashes.values()).issubset(copied_hashes):
        raise PlanError("草稿內素材與來源檔的 SHA-256 不符")
    saved_font_hashes: set[str] = set()
    for material in saved.get("materials", {}).get("texts", []):
        raw = material.get("font_path")
        if not raw:
            continue
        path = Path(raw)
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(output.resolve()):
            raise PlanError(f"保存後字體未指向草稿副本：{raw}")
        saved_font_hashes.add(file_sha256(path))
    used_font_sources = {item.get("font", str(font) if font else None)
                         for track in plan["tracks"] if track["type"] == "text"
                         for item in track["segments"]}
    expected_font_hashes = {file_sha256(Path(raw)) for raw in used_font_sources if raw}
    if not expected_font_hashes.issubset(saved_font_hashes):
        raise PlanError("草稿內字體與來源檔的 SHA-256 不符")
    if any(file_sha256(Path(source)) != expected for source, expected in source_hashes.items()):
        raise PlanError("建立草稿期間來源素材曾改變")
    if any(file_sha256(Path(source)) != expected for source, expected in font_hashes.items()):
        raise PlanError("建立草稿期間來源字體曾改變")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--draft-root", type=Path, help="剪映設定中顯示的草稿根目錄")
    parser.add_argument("--user-data", type=Path, help="可選：JianyingPro User Data 目錄，用於首頁登記")
    parser.add_argument("--font", type=Path, help="可選：本機字體檔")
    parser.add_argument("--write", action="store_true", help="實際建立新草稿；預設僅檢查")
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_text(encoding="utf-8-sig"),
                          object_pairs_hook=unique_object,
                          parse_constant=lambda item: (_ for _ in ()).throw(
                              PlanError(f"不允許非有限 JSON 數字：{item}")))
        report = validate(plan)
        if args.write:
            if args.draft_root is None:
                raise PlanError("--write 需要 --draft-root")
            result = create(plan, args.draft_root, args.user_data, args.font)
            report.update({"status": "saved-unverified-in-app", "draft_info": str(result),
                           "sha256": hashlib.sha256(result.read_bytes()).hexdigest()})
        else:
            report["status"] = "plan-valid"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, PlanError, ValueError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

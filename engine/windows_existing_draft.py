"""檢查本機剪映草稿，並在工作區新副本上編輯本工具產生的明文草稿。

inspect 為唯讀操作，會列出全部檔案及 SHA-256。edit 僅接受未經剪映保存的
draft_info.json、draft_meta_info.json 與單層 materials 草稿；預設 dry-run。
剪映保存後的加密、多時間線、雲端及未知效果草稿一律拒絕編輯。
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from typing import Any

from windows_draft_bridge import PlanError, clean_name, file_sha256, number, unique_object
from windows_draft_install import read_object, relocated_documents, source_files


ALLOWED_NONEMPTY_MATERIALS = {"videos", "audios", "texts", "speeds"}


def _is_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def file_snapshot(source: Path) -> dict[Path, dict[str, Any]]:
    """Read every ordinary file, with no traversal through links or junctions."""
    if not source.is_dir() or _is_link(source):
        raise PlanError(f"草稿資料夾不存在或是連結：{source}")
    result: dict[Path, dict[str, Any]] = {}
    for base, dirs, files in os.walk(source, topdown=True, followlinks=False):
        folder = Path(base)
        for name in dirs:
            path = folder / name
            if _is_link(path):
                raise PlanError(f"草稿包含連結或接合點：{path}")
        for name in files:
            path = folder / name
            if _is_link(path) or not path.is_file():
                raise PlanError(f"草稿包含連結或非一般檔案：{path}")
            result[path.relative_to(source)] = {"sha256": file_sha256(path),
                                                  "size": path.stat().st_size}
    return result


def _try_plaintext(path: Path) -> tuple[dict[str, Any] | None, dict[str, str]]:
    if not path.is_file():
        return None, {"encoding": "missing"}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"),
                           object_pairs_hook=unique_object)
    except (OSError, UnicodeError, ValueError) as exc:
        return None, {"encoding": "encrypted-or-unsupported", "reason": str(exc)}
    if not isinstance(value, dict):
        return None, {"encoding": "unsupported-json-root"}
    return value, {"encoding": "plaintext-json"}


def _reference_status(raw: str, source: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": raw, "available": False, "inside_draft": False}
    try:
        path = Path(raw)
        if path.is_absolute():
            result["available"] = path.is_file() and not _is_link(path)
            result["inside_draft"] = path.resolve().is_relative_to(source.resolve())
    except (OSError, ValueError):
        pass
    return result


def _known_references(document: dict[str, Any]) -> list[str]:
    try:
        from pyJianYingDraft.draft_file_paths import map_draft_file_paths
    except ImportError as exc:
        raise PlanError("缺少固定版本的 pyJianYingDraft") from exc
    paths: list[str] = []

    def collect(raw: str) -> str:
        paths.append(raw)
        return raw

    map_draft_file_paths(deepcopy(document), collect)
    return paths


def inspect_draft(source: Path) -> dict[str, Any]:
    source = source.absolute()
    snapshot = file_snapshot(source)
    info, info_state = _try_plaintext(source / "draft_info.json")
    meta, meta_state = _try_plaintext(source / "draft_meta_info.json")
    report: dict[str, Any] = {
        "status": "inspected-read-only", "source": str(source),
        "file_count": len(snapshot),
        "files": [{"path": rel.as_posix(), **record}
                  for rel, record in sorted(snapshot.items(), key=lambda pair: pair[0].as_posix())],
        "draft_info": info_state, "draft_meta_info": meta_state,
    }
    if (source / "draft_content.json").exists() or (source / "Timelines").exists():
        report["timeline_authority"] = "unknown-encrypted-ui-mirrors"
        report["warning"] = ("剪映保存後的 draft_info.json 可能舊於實際時間軸；"
                             "本檢查不以它推定最新編輯內容")
    else:
        report["timeline_authority"] = "draft_info-json-unverified-in-app"
    if info is not None:
        tracks = info.get("tracks")
        materials = info.get("materials")
        report["draft_info"].update({
            "id": info.get("id"), "version": info.get("version"),
            "track_count": len(tracks) if isinstance(tracks, list) else None,
            "material_counts": {key: len(value) for key, value in materials.items()
                                if isinstance(value, list) and value}
                               if isinstance(materials, dict) else None,
        })
        if isinstance(tracks, list):
            text_by_id = {}
            if isinstance(materials, dict) and isinstance(materials.get("texts"), list):
                for material in materials["texts"]:
                    if isinstance(material, dict) and isinstance(material.get("id"), str):
                        try:
                            text_by_id[material["id"]] = json.loads(material["content"])["text"]
                        except (KeyError, TypeError, ValueError):
                            pass
            report["tracks"] = []
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                segments = track.get("segments")
                report["tracks"].append({
                    "id": track.get("id"), "name": track.get("name"), "type": track.get("type"),
                    "segments": [{"id": seg.get("id"), "material_id": seg.get("material_id"),
                                  "text": text_by_id.get(seg.get("material_id"))}
                                 for seg in segments if isinstance(seg, dict)]
                    if isinstance(segments, list) else None,
                })
    if meta is not None:
        report["draft_meta_info"].update({"draft_id": meta.get("draft_id"),
                                           "draft_name": meta.get("draft_name")})
    paths: set[str] = set()
    for document in (info, meta):
        if document is None:
            continue
        try:
            paths.update(_known_references(document))
        except (PlanError, ValueError, TypeError) as exc:
            report["path_scan_error"] = str(exc)
    report["material_paths"] = [_reference_status(raw, source) for raw in sorted(paths)]
    if file_snapshot(source) != snapshot:
        raise PlanError("檢查期間草稿檔案已改變，請重新執行")
    return report


def _editable_structure(source: Path, target: Path) -> tuple[dict[str, Any], dict[str, Any],
                                                               dict[Path, str]]:
    if {entry.name for entry in source.iterdir()} - {
        "draft_info.json", "draft_meta_info.json", "materials"
    } or not (source / "materials").is_dir():
        raise PlanError("草稿含未知檔案或目錄；只可編輯本工具未經剪映保存的草稿")
    if any(entry.is_dir() for entry in (source / "materials").iterdir()):
        raise PlanError("materials 內含未知子目錄")
    files = source_files(source)
    info, meta, references = relocated_documents(source, target)
    if not isinstance(info.get("tracks"), list) or not isinstance(info.get("materials"), dict):
        raise PlanError("草稿沒有可識別的單時間線軌道及素材")
    if info.get("id") != meta.get("draft_id") or not isinstance(info.get("id"), str):
        raise PlanError("草稿主檔與中繼資料 ID 不一致")
    if info.get("relationships") or info.get("keyframe_graph_list"):
        raise PlanError("多時間線、關聯素材或未知動畫圖形尚不支援編輯")
    materials = info["materials"]
    if any(not isinstance(value, list) for value in materials.values()):
        raise PlanError("素材清單格式未知")
    populated = {key for key, value in materials.items() if value}
    if populated - ALLOWED_NONEMPTY_MATERIALS:
        raise PlanError(f"草稿含未知效果或素材：{', '.join(sorted(populated - ALLOWED_NONEMPTY_MATERIALS))}")
    material_ids: dict[str, str] = {}
    for bucket in ALLOWED_NONEMPTY_MATERIALS:
        for material in materials.get(bucket, []):
            if not isinstance(material, dict) or not isinstance(material.get("id"), str):
                raise PlanError("素材 ID 或格式未知")
            if material["id"] in material_ids:
                raise PlanError("素材 ID 重複")
            material_ids[material["id"]] = bucket
            if bucket in {"videos", "audios"}:
                expected_types = {"video", "photo", "gif"} if bucket == "videos" else {"extract_music"}
                if material.get("type") not in expected_types:
                    raise PlanError("草稿含雲端或未知媒體素材")
                raw_path = material.get("path")
                if (not isinstance(raw_path, str) or not Path(raw_path).is_absolute()
                        or not Path(raw_path).is_relative_to(target)):
                    raise PlanError("媒體素材未內嵌於草稿副本")
            if bucket == "texts":
                if material.get("type") != "text":
                    raise PlanError("草稿含未知文字素材類型")
                if material.get("font_resource_id") or material.get("font_id"):
                    raise PlanError("雲端文字字體尚不支援編輯")
            if bucket == "speeds" and material.get("type") != "speed":
                raise PlanError("草稿含未知速度素材類型")
    track_ids: set[str] = set()
    segment_ids: set[str] = set()
    for track in info["tracks"]:
        if not isinstance(track, dict) or track.get("type") not in {"video", "audio", "text"}:
            raise PlanError("草稿含未知軌道類型")
        if not isinstance(track.get("id"), str) or track["id"] in track_ids:
            raise PlanError("軌道 ID 缺失或重複")
        track_ids.add(track["id"])
        if not isinstance(track.get("segments"), list):
            raise PlanError("軌道片段格式未知")
        expected_bucket = {"video": "videos", "audio": "audios", "text": "texts"}[track["type"]]
        for seg in track["segments"]:
            if not isinstance(seg, dict) or not isinstance(seg.get("id"), str):
                raise PlanError("片段 ID 或格式未知")
            if seg["id"] in segment_ids:
                raise PlanError("片段 ID 重複")
            segment_ids.add(seg["id"])
            if material_ids.get(seg.get("material_id")) != expected_bucket:
                raise PlanError("片段素材參照遺失或類型不符")
            refs = seg.get("extra_material_refs", [])
            if not isinstance(refs, list) or any(material_ids.get(ref) != "speeds" for ref in refs):
                raise PlanError("片段連結了未知效果或素材")
    embedded = {rel for rel in files if rel.parts[0] == "materials"}
    if embedded != references:
        raise PlanError("草稿含未引用素材，或引用了未知路徑")
    return info, meta, files


def _index(info: dict[str, Any]) -> tuple[dict[str, dict[str, Any]],
                                          dict[str, tuple[str, dict[str, Any]]],
                                          dict[str, dict[str, Any]], dict[str, int]]:
    tracks = {track["id"]: track for track in info["tracks"]}
    segments = {seg["id"]: (track["type"], seg) for track in info["tracks"]
                for seg in track["segments"]}
    texts = {material["id"]: material for material in info["materials"].get("texts", [])}
    refs: dict[str, int] = {}
    for _kind, seg in segments.values():
        mid = seg["material_id"]
        refs[mid] = refs.get(mid, 0) + 1
    return tracks, segments, texts, refs


def _replace_text(material: dict[str, Any], value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PlanError("替換文字必須是非空字串")
    try:
        content = json.loads(material["content"], object_pairs_hook=unique_object)
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanError("文字素材不是可識別的明文 rich-text") from exc
    if not isinstance(content, dict) or set(content) != {"styles", "text"}:
        raise PlanError("文字內容含未知欄位")
    old = content["text"]
    styles = content["styles"]
    if not isinstance(old, str) or not isinstance(styles, list) or not styles:
        raise PlanError("文字樣式格式未知")
    old_length = len(old.encode("utf-16-le")) // 2
    new_length = len(value.encode("utf-16-le")) // 2
    if any(not isinstance(style, dict) or style.get("range") != [0, old_length]
           for style in styles):
        raise PlanError("局部文字樣式需要專用範圍對應，目前不可修改")
    content["text"] = value
    for style in styles:
        style["range"] = [0, new_length]
    # 路徑重綁器會以相同格式回寫 rich-text；保持回讀結果可直接比較。
    material["content"] = json.dumps(content, ensure_ascii=False)


def _apply_operations(info: dict[str, Any], operations: Any) -> list[dict[str, Any]]:
    if not isinstance(operations, list) or not operations:
        raise PlanError("編輯操作必須是非空陣列")
    applied: list[dict[str, Any]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise PlanError("編輯操作必須是物件")
        tracks, segments, texts, refs = _index(info)
        op = operation.get("op")
        identifier = operation.get("id")
        if not isinstance(identifier, str):
            raise PlanError("操作必須指定精確的軌道或片段 ID")
        if op == "replace_text":
            if set(operation) != {"op", "id", "text"} or identifier not in segments:
                raise PlanError("replace_text 必須指定文字片段 ID 與 text")
            kind, seg = segments[identifier]
            mid = seg["material_id"]
            if kind != "text" or mid not in texts or refs[mid] != 1:
                raise PlanError("文字片段的素材不唯一或類型不符")
            _replace_text(texts[mid], operation["text"])
            applied.append({"op": op, "id": identifier, "material_id": mid})
        elif op == "rename_track":
            if set(operation) != {"op", "id", "name"} or identifier not in tracks:
                raise PlanError("rename_track 必須指定軌道 ID 與 name")
            name = clean_name(operation["name"], "軌道名稱")
            if any(track["name"] == name and track_id != identifier
                   for track_id, track in tracks.items()):
                raise PlanError("軌道名稱重複")
            tracks[identifier]["name"] = name
            tracks[identifier]["is_default_name"] = False
            applied.append({"op": op, "id": identifier, "name": name})
        elif op == "set_segment":
            if set(operation) != {"op", "id", "set"} or identifier not in segments:
                raise PlanError("set_segment 必須指定片段 ID 與 set")
            kind, seg = segments[identifier]
            fields = operation["set"]
            allowed = {"volume"} if kind == "audio" else {"x", "y"} if kind == "text" else {"volume", "x", "y"}
            if not isinstance(fields, dict) or not fields or set(fields) - allowed:
                raise PlanError(f"此片段只支援修改：{', '.join(sorted(allowed))}")
            if seg.get("common_keyframes") or seg.get("keyframe_refs"):
                raise PlanError("含關鍵影格的片段不可修改靜態音量或位置")
            for field, raw in fields.items():
                value = number(raw, field, 0 if field == "volume" else -5,
                               4 if field == "volume" else 5)
                if field == "volume":
                    seg["volume"] = value
                    seg["last_nonzero_volume"] = value if value > 0 else seg.get("last_nonzero_volume", 1)
                else:
                    clip = seg.get("clip")
                    if not isinstance(clip, dict) or not isinstance(clip.get("transform"), dict):
                        raise PlanError("片段位置格式未知")
                    clip["transform"][field] = value
            applied.append({"op": op, "id": identifier, "set": fields})
        else:
            raise PlanError(f"尚未支援的編輯操作：{op}")
    return applied


def _check_target(source: Path, target: Path, workspace: Path) -> None:
    if not workspace.is_dir() or _is_link(workspace):
        raise PlanError(f"工作區不存在或是連結：{workspace}")
    if not target.parent.is_dir() or _is_link(target.parent):
        raise PlanError(f"副本的父目錄不存在或是連結：{target.parent}")
    source_real = source.resolve(strict=True)
    target_real = target.absolute()
    if target_real.exists() or _is_link(target_real):
        raise PlanError(f"目標已存在，不覆寫：{target_real}")
    parent_real = target.parent.resolve(strict=True)
    workspace_real = workspace.resolve(strict=True)
    if not parent_real.is_relative_to(workspace_real):
        raise PlanError("編輯副本必須位於指定工作區內")
    if parent_real.is_relative_to(source_real) or source_real.is_relative_to(parent_real / target.name):
        raise PlanError("副本位置不可與原草稿重疊")
    clean_name(target.name, "副本名稱")
    for ancestor in [target.parent, *target.parent.parents]:
        if ancestor == workspace or ancestor == workspace_real:
            break
        if _is_link(ancestor):
            raise PlanError(f"目標路徑包含連結或接合點：{ancestor}")


def edit_draft(source: Path, target: Path, operations: Any, write: bool,
               workspace: Path | None = None) -> dict[str, Any]:
    if sys.platform != "win32":
        raise PlanError("草稿編輯只支援 Windows")
    source = source.absolute()
    target = target.absolute()
    workspace = Path.cwd() if workspace is None else workspace.absolute()
    _check_target(source, target, workspace)
    original = file_snapshot(source)
    info, meta, hashes = _editable_structure(source, target)
    applied = _apply_operations(info, operations)
    draft_id = str(uuid.uuid4()).upper()
    info["id"] = draft_id
    meta["draft_id"] = draft_id
    if info.get("name"):
        info["name"] = target.name
    meta["draft_name"] = target.name
    report: dict[str, Any] = {
        "status": "validated-dry-run", "source": str(source), "target": str(target),
        "source_files": len(original), "operations": applied,
    }
    if file_snapshot(source) != original:
        raise PlanError("驗證期間原草稿發生變化")
    if not write:
        return report

    staging = target.parent / f".{target.name}.edit-{uuid.uuid4().hex}"
    renamed = False
    try:
        shutil.copytree(source, staging, symlinks=False)
        for rel, expected in hashes.items():
            if file_sha256(staging / rel) != expected:
                raise PlanError(f"複製後檔案雜湊不符：{rel}")
        for filename, document in (("draft_info.json", info), ("draft_meta_info.json", meta)):
            (staging / filename).write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8")
        if file_snapshot(source) != original:
            raise PlanError("複製期間原草稿發生變化")
        if target.exists() or _is_link(target):
            raise PlanError(f"目標已存在，不覆寫：{target}")
        staging.rename(target)
        renamed = True
        # 重新讀取兩個文檔，並確認所有素材現在指向新副本。
        verified_info, verified_meta, copied = _editable_structure(target, target)
        if verified_info != info or verified_meta != meta:
            raise PlanError("副本回讀內容與預期不符")
        for rel, expected in hashes.items():
            if rel.parts[0] == "materials" and copied[rel] != expected:
                raise PlanError(f"副本素材雜湊不符：{rel}")
        if file_snapshot(source) != original:
            raise PlanError("編輯後原草稿發生變化")
    except Exception:
        if renamed and target.is_dir() and not _is_link(target) and not staging.exists():
            target.rename(staging)
        raise
    finally:
        if staging.exists():
            if staging.resolve().parent != target.parent.resolve() or _is_link(staging):
                raise PlanError("暫存目錄位置異常，請人工檢查")
            shutil.rmtree(staging)
    report["status"] = "copied-edited-unverified-in-app"
    report["draft_info"] = str(target / "draft_info.json")
    report["draft_id"] = draft_id
    report["source_unchanged"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect", help="唯讀列出草稿檔案、雜湊和已知素材")
    inspect_parser.add_argument("--source", type=Path, required=True)
    edit_parser = sub.add_parser("edit", help="在工作區建立經驗證的新草稿副本")
    edit_parser.add_argument("--source", type=Path, required=True)
    edit_parser.add_argument("--target", type=Path, required=True)
    edit_parser.add_argument("--operations", type=Path, required=True, help="JSON 操作陣列")
    edit_parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="副本允許存放的工作區根目錄")
    edit_parser.add_argument("--write", action="store_true", help="實際建立副本；預設 dry-run")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect_draft(args.source)
        else:
            operations = json.loads(args.operations.read_text(encoding="utf-8-sig"),
                                    object_pairs_hook=unique_object)
            result = edit_draft(args.source, args.target, operations, args.write, args.workspace)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, PlanError, ValueError, TypeError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

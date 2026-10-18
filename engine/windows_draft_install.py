"""把本轉接器產生的 Windows 剪映草稿複製到新位置並重綁素材路徑。

只接受草稿主檔、中繼資料與 materials 目錄；預設僅檢查，--write 才安裝。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from windows_draft_bridge import PlanError, clean_name, file_sha256, unique_object


def read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"),
                           object_pairs_hook=unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PlanError(f"無法讀取明文 JSON：{path}") from exc
    if not isinstance(value, dict):
        raise PlanError(f"JSON 主體必須是物件：{path}")
    return value


def source_files(source: Path) -> dict[Path, str]:
    if not source.is_dir() or source.is_symlink():
        raise PlanError(f"草稿來源不存在或是連結：{source}")
    files: dict[Path, str] = {}
    for path in source.rglob("*"):
        if path.is_symlink():
            raise PlanError(f"草稿來源含符號連結：{path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PlanError(f"草稿來源含非一般檔案：{path}")
        rel = path.relative_to(source)
        if rel.name not in {"draft_info.json", "draft_meta_info.json"} and rel.parts[0] != "materials":
            raise PlanError(f"此安裝器只處理未經剪映修改的草稿：{rel}")
        if rel.parts[0] == "materials" and len(rel.parts) != 2:
            raise PlanError(f"materials 只能有一層檔案：{rel}")
        files[rel] = file_sha256(path)
    if not {Path("draft_info.json"), Path("draft_meta_info.json")}.issubset(files):
        raise PlanError("草稿主檔或中繼資料缺失")
    if not any(rel.parts[0] == "materials" for rel in files):
        raise PlanError("草稿沒有內嵌素材")
    return files


def relocated_documents(source: Path, target: Path) -> tuple[dict[str, Any], dict[str, Any], set[Path]]:
    try:
        from pyJianYingDraft.draft_file_paths import map_draft_file_paths
    except ImportError as exc:
        raise PlanError("缺少固定版本的 pyJianYingDraft") from exc

    info = read_object(source / "draft_info.json")
    meta = read_object(source / "draft_meta_info.json")
    if meta.get("draft_name") != source.name:
        raise PlanError("草稿資料夾與中繼資料名稱不一致")
    source_real = source.resolve(strict=True)
    references: set[Path] = set()

    def replace(raw: str) -> str:
        path = Path(raw)
        if not path.is_absolute() or not path.is_file() or path.is_symlink():
            raise PlanError(f"本機素材路徑無效：{raw}")
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(source_real):
            raise PlanError(f"素材未內嵌於來源草稿：{raw}")
        rel = resolved.relative_to(source_real)
        if len(rel.parts) != 2 or rel.parts[0] != "materials":
            raise PlanError(f"素材不在草稿 materials 目錄：{raw}")
        references.add(rel)
        return str(target / rel)

    map_draft_file_paths(info, replace)
    map_draft_file_paths(meta, replace)
    if not references:
        raise PlanError("草稿中找不到本機素材路徑")
    meta["draft_fold_path"] = str(target)
    meta["draft_root_path"] = str(target.parent)
    return info, meta, references


def install(source: Path, root: Path, write: bool) -> dict[str, Any]:
    if sys.platform != "win32":
        raise PlanError("此安裝器只支援 Windows")
    if not root.is_dir() or root.is_symlink():
        raise PlanError(f"草稿根目錄不存在或是連結：{root}")
    name = clean_name(source.name, "草稿名稱")
    source_real = source.resolve(strict=True)
    root_real = root.resolve(strict=True)
    root_path = root.absolute()
    if root_real.is_relative_to(source_real):
        raise PlanError("目標根目錄不可位於來源草稿內")
    if source_real.parent == root_real:
        raise PlanError("來源草稿已在目標根目錄中")
    # 保留使用者在剪映設定中看到的磁碟代號；D: 可能指向同一磁碟的 E:。
    target = root_path / name
    if target.exists() or target.is_symlink():
        raise PlanError(f"目標草稿已存在，不覆寫：{target}")
    files = source_files(source)
    info, meta, references = relocated_documents(source, target)
    report = {"name": name, "target": str(target), "files": len(files),
              "materials": len(references), "status": "validated"}
    if not write:
        return report

    staging = root_path / f".{name}.install-{uuid.uuid4().hex}"
    try:
        shutil.copytree(source, staging, symlinks=False)
        for rel, expected in files.items():
            if file_sha256(staging / rel) != expected:
                raise PlanError(f"複製後檔案雜湊不符：{rel}")
        for filename, document in (("draft_info.json", info), ("draft_meta_info.json", meta)):
            (staging / filename).write_text(
                json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8")
        for rel in references:
            if file_sha256(staging / rel) != files[rel]:
                raise PlanError(f"素材核對失敗：{rel}")
        if target.exists() or target.is_symlink():
            raise PlanError(f"目標草稿已存在，不覆寫：{target}")
        staging.rename(target)
    finally:
        if staging.exists():
            if staging.resolve().parent != root_real or staging.is_symlink():
                raise PlanError("暫存目錄位置異常，請人工檢查")
            shutil.rmtree(staging)
    report["status"] = "installed-unverified-in-app"
    report["draft_info_sha256"] = hashlib.sha256((target / "draft_info.json").read_bytes()).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="已解壓的草稿資料夾")
    parser.add_argument("--draft-root", type=Path, required=True, help="剪映設定顯示的草稿根目錄")
    parser.add_argument("--write", action="store_true", help="複製並重綁；預設僅檢查")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.source, args.draft_root, args.write),
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, PlanError, ValueError) as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

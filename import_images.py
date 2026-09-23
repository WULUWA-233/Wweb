"""Validate and import the bundled platform-photo manifest into SQLite.

The image binaries are kept under ``static/img/platforms``.  This importer
stores only verified local paths and provenance metadata in ``platform_images``.
It is intentionally idempotent: the same ``(platform, local_path)`` row is
updated in place instead of being duplicated.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from manage_images import (
    IMAGE_TYPES,
    ImageManagerError,
    validate_http_url,
    validate_local_path,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "platforms.sqlite3"
DEFAULT_MANIFEST = ROOT / "data" / "platform_image_manifest.csv"
DEFAULT_STATIC_ROOT = ROOT / "static"

REQUIRED_COLUMNS = {
    "platform_name",
    "local_path",
    "caption",
    "source_url",
    "source_name",
    "image_type",
    "is_primary",
    "sort_order",
}


class ImageImportError(ValueError):
    """Raised when the manifest, image files, or target database are invalid."""


@dataclass(frozen=True)
class ImageRecord:
    platform_id: int
    platform_name: str
    local_path: str
    caption: str
    source_url: str
    source_name: str
    image_type: str
    is_primary: int
    sort_order: int


def _required_text(row: dict[str, str], field: str, row_number: int) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ImageImportError(f"清单第 {row_number} 行的 {field} 为空。")
    return value


def _parse_flag(value: str, field: str, row_number: int) -> int:
    normalized = value.strip()
    if normalized not in {"0", "1"}:
        raise ImageImportError(f"清单第 {row_number} 行的 {field} 必须是 0 或 1。")
    return int(normalized)


def _parse_sort_order(value: str, row_number: int) -> int:
    try:
        result = int(value.strip(), 10)
    except ValueError as exc:
        raise ImageImportError(f"清单第 {row_number} 行的 sort_order 必须是非负整数。") from exc
    if result < 0:
        raise ImageImportError(f"清单第 {row_number} 行的 sort_order 必须是非负整数。")
    return result


def _detected_extension(path: Path) -> str:
    """Return a browser-safe extension from the file signature.

    The collection contains source downloads whose original names all ended in
    ``.jpg`` even when their actual encodings were WebP or AVIF.  Verifying the
    signature here prevents Flask from serving those files with a mismatched
    MIME type.
    """

    with path.open("rb") as handle:
        header = handle.read(32)
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return ".webp"
    if len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] in {b"avif", b"avis"}:
        return ".avif"
    raise ImageImportError(f"图片格式未识别：{path}")


def _validate_image_file(static_root: Path, local_path: str, row_number: int) -> None:
    static_root = static_root.resolve()
    file_path = (static_root / Path(*Path(local_path).parts)).resolve()
    try:
        file_path.relative_to(static_root)
    except ValueError as exc:
        raise ImageImportError(f"清单第 {row_number} 行的图片路径超出 static 目录。") from exc
    if not file_path.is_file():
        raise ImageImportError(f"清单第 {row_number} 行的图片文件不存在：{file_path}")
    actual_extension = _detected_extension(file_path)
    declared_extension = file_path.suffix.lower()
    if declared_extension == ".jpeg":
        declared_extension = ".jpg"
    if declared_extension != actual_extension:
        raise ImageImportError(
            f"清单第 {row_number} 行的图片扩展名与实际格式不一致："
            f"{file_path.name}（实际 {actual_extension}）"
        )


def _open_database(db_path: Path) -> sqlite3.Connection:
    path = db_path.expanduser().resolve()
    if not path.is_file():
        raise ImageImportError(f"数据库文件不存在：{path}；请先运行 python import_data.py。")
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    required_tables = {"platforms", "platform_images"}
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('platforms','platform_images')"
        )
    }
    if tables != required_tables:
        db.close()
        raise ImageImportError("数据库结构不完整；请先运行 python import_data.py 和 python migrate.py。")
    return db


def _load_records(
    db: sqlite3.Connection,
    manifest_path: Path,
    static_root: Path,
) -> list[ImageRecord]:
    if not manifest_path.is_file():
        raise ImageImportError(f"图片清单不存在：{manifest_path}")
    if not static_root.is_dir():
        raise ImageImportError(f"static 目录不存在：{static_root}")

    platforms = {
        row["name"]: int(row["id"])
        for row in db.execute("SELECT id, name FROM platforms ORDER BY id")
    }
    records: list[ImageRecord] = []
    seen_platforms: set[str] = set()
    seen_paths: set[str] = set()
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or ())
        missing_columns = sorted(REQUIRED_COLUMNS - columns)
        if missing_columns:
            raise ImageImportError("图片清单缺少字段：" + "、".join(missing_columns))

        for row_number, row in enumerate(reader, start=2):
            platform_name = _required_text(row, "platform_name", row_number)
            if platform_name not in platforms:
                raise ImageImportError(
                    f"清单第 {row_number} 行的平台不在数据库中：{platform_name}"
                )
            if platform_name in seen_platforms:
                raise ImageImportError(f"图片清单的平台重复：{platform_name}")

            try:
                local_path = validate_local_path(
                    _required_text(row, "local_path", row_number)
                )
                source_url = validate_http_url(
                    _required_text(row, "source_url", row_number), "source_url"
                )
            except (ImageManagerError, ValueError) as exc:
                raise ImageImportError(f"清单第 {row_number} 行校验失败：{exc}") from exc
            if local_path in seen_paths:
                raise ImageImportError(f"图片清单的本地路径重复：{local_path}")
            _validate_image_file(static_root, local_path, row_number)

            image_type = _required_text(row, "image_type", row_number)
            if image_type not in IMAGE_TYPES:
                raise ImageImportError(
                    f"清单第 {row_number} 行的 image_type 不在允许范围：{image_type}"
                )
            record = ImageRecord(
                platform_id=platforms[platform_name],
                platform_name=platform_name,
                local_path=local_path,
                caption=_required_text(row, "caption", row_number),
                source_url=source_url,
                source_name=_required_text(row, "source_name", row_number),
                image_type=image_type,
                is_primary=_parse_flag(row.get("is_primary") or "", "is_primary", row_number),
                sort_order=_parse_sort_order(row.get("sort_order") or "", row_number),
            )
            seen_platforms.add(platform_name)
            seen_paths.add(local_path)
            records.append(record)

    if not records:
        raise ImageImportError("图片清单没有数据行。")
    duplicate_primary = [
        name
        for name in seen_platforms
        if sum(record.is_primary for record in records if record.platform_name == name) > 1
    ]
    if duplicate_primary:
        raise ImageImportError("每个平台最多一张主图：" + "、".join(sorted(duplicate_primary)))

    # A malformed pre-existing duplicate would make an idempotent update
    # ambiguous, so reject it before entering the write transaction.
    for record in records:
        count = db.execute(
            "SELECT COUNT(*) FROM platform_images WHERE platform_id=? AND local_path=?",
            (record.platform_id, record.local_path),
        ).fetchone()[0]
        if count > 1:
            raise ImageImportError(
                f"数据库中已有重复图片记录：{record.platform_name} / {record.local_path}"
            )
    return records


def import_images(
    db_path: Path | str = DEFAULT_DB,
    manifest_path: Path | str = DEFAULT_MANIFEST,
    static_root: Path | str = DEFAULT_STATIC_ROOT,
) -> dict[str, int]:
    """Validate the whole manifest, then insert or update it atomically."""

    db_path = Path(db_path)
    manifest_path = Path(manifest_path)
    static_root = Path(static_root)
    db = _open_database(db_path)
    try:
        records = _load_records(db, manifest_path, static_root)
        inserted = 0
        updated = 0
        try:
            with db:
                for platform_id in {record.platform_id for record in records if record.is_primary}:
                    db.execute(
                        "UPDATE platform_images SET is_primary=0 WHERE platform_id=?",
                        (platform_id,),
                    )
                for record in records:
                    existing = db.execute(
                        "SELECT id FROM platform_images WHERE platform_id=? AND local_path=?",
                        (record.platform_id, record.local_path),
                    ).fetchone()
                    values = (
                        record.caption,
                        record.source_url,
                        record.source_name,
                        record.image_type,
                        record.is_primary,
                        record.sort_order,
                    )
                    if existing:
                        db.execute(
                            "UPDATE platform_images SET image_url=NULL, caption=?, source_url=?, "
                            "source_name=?, image_type=?, is_primary=?, sort_order=? WHERE id=?",
                            (*values, existing["id"]),
                        )
                        updated += 1
                    else:
                        db.execute(
                            "INSERT INTO platform_images "
                            "(platform_id,image_url,local_path,caption,source_url,source_name,"
                            "image_type,is_primary,sort_order) VALUES (?,NULL,?,?,?,?,?,?,?)",
                            (
                                record.platform_id,
                                record.local_path,
                                record.caption,
                                record.source_url,
                                record.source_name,
                                record.image_type,
                                record.is_primary,
                                record.sort_order,
                            ),
                        )
                        inserted += 1
        except sqlite3.DatabaseError as exc:
            raise ImageImportError(f"图片元数据写入失败，事务已回滚：{exc}") from exc
        return {"inserted": inserted, "updated": updated, "total": len(records)}
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="批量导入平台主展示图及来源信息")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 数据库路径")
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST, help="UTF-8 CSV 图片清单路径"
    )
    parser.add_argument(
        "--static-root", type=Path, default=DEFAULT_STATIC_ROOT, help="网站 static 目录"
    )
    args = parser.parse_args()
    try:
        result = import_images(args.db, args.manifest, args.static_root)
    except ImageImportError as exc:
        parser.exit(1, f"图片导入失败：{exc}\n")
    print(
        "图片导入完成："
        f"新增 {result['inserted']}，更新 {result['updated']}，清单共 {result['total']} 条。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Manage verified platform-image metadata in the SQLite catalogue.

Examples:
    python manage_images.py list --platform-id 1
    python manage_images.py add --platform-id 1 \
        --local-path img/platforms/example/official-01.jpg \
        --caption "Official view" --image-type official --primary
    python manage_images.py set-primary 12
    python manage_images.py delete 12
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / "data" / "platforms.sqlite3"
IMAGE_TYPES = (
    "official",
    "exercise",
    "combat",
    "manufacturer",
    "control",
    "loading",
    "other",
)


class ImageManagerError(RuntimeError):
    """An expected command or data validation error."""


def positive_id(value: str) -> int:
    """Argparse converter for positive SQLite identifiers."""
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是正整数") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return parsed


def nonnegative_int(value: str) -> int:
    """Argparse converter for non-negative ordering values."""
    try:
        parsed = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是非负整数") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("必须是非负整数")
    return parsed


def validate_http_url(value: str, field_name: str) -> str:
    """Return a trimmed, absolute HTTP(S) URL or raise a clear error."""
    url = value.strip()
    if not url:
        raise ImageManagerError(f"{field_name} 不能为空。")
    if any(character.isspace() or ord(character) < 32 for character in url):
        raise ImageManagerError(f"{field_name} 含空白或控制字符：{value!r}")

    try:
        parsed = urlsplit(url)
        port = parsed.port  # Force validation of malformed ports.
    except ValueError as exc:
        raise ImageManagerError(f"{field_name} 格式错误：{value!r}") from exc

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ImageManagerError(f"{field_name} 必须是完整的 http:// 或 https:// URL。")
    if parsed.username is not None or parsed.password is not None:
        raise ImageManagerError(f"{field_name} 不得包含用户名或密码。")
    if port is not None and not (1 <= port <= 65535):
        raise ImageManagerError(f"{field_name} 端口超出有效范围。")
    return url


def validate_local_path(value: str) -> str:
    """Validate a static path confined to ``img/platforms/``."""
    path_text = value.strip()
    if path_text != value or not path_text:
        raise ImageManagerError("local-path 不能为空，也不得带首尾空白。")
    if "\\" in path_text:
        raise ImageManagerError("local-path 必须使用正斜杠 /，不得使用反斜杠。")
    if any(ord(character) < 32 for character in path_text):
        raise ImageManagerError("local-path 含控制字符。")
    if "//" in path_text:
        raise ImageManagerError("local-path 不得包含空路径段 //。")

    path = PurePosixPath(path_text)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ImageManagerError("local-path 必须是 img/platforms/ 下的相对路径，且不得包含 . 或 ..。")
    if len(path.parts) < 3 or path.parts[:2] != ("img", "platforms"):
        raise ImageManagerError("local-path 仅允许 img/platforms/... 范围内的文件。")
    if path_text.endswith("/"):
        raise ImageManagerError("local-path 必须指向文件，不能以 / 结尾。")
    return path_text


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def open_database(db_path: Path) -> sqlite3.Connection:
    path = Path(db_path).expanduser()
    if not path.is_file():
        raise ImageManagerError(f"数据库文件不存在：{path}")

    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    foreign_keys = db.execute("PRAGMA foreign_keys").fetchone()[0]
    if foreign_keys != 1:
        db.close()
        raise ImageManagerError("SQLite 外键约束未成功启用。")
    table_exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'platform_images'"
    ).fetchone()
    if not table_exists:
        db.close()
        raise ImageManagerError("数据库缺少 platform_images 表；请先运行 python migrate.py。")
    return db


def ensure_platform(db: sqlite3.Connection, platform_id: int) -> sqlite3.Row:
    row = db.execute(
        "SELECT id, name FROM platforms WHERE id = ?", (platform_id,)
    ).fetchone()
    if row is None:
        raise ImageManagerError(f"平台 ID {platform_id} 不存在。")
    return row


def ensure_image(db: sqlite3.Connection, image_id: int) -> sqlite3.Row:
    row = db.execute(
        "SELECT id, platform_id, is_primary FROM platform_images WHERE id = ?",
        (image_id,),
    ).fetchone()
    if row is None:
        raise ImageManagerError(f"图片 ID {image_id} 不存在。")
    return row


def command_list(db: sqlite3.Connection, args: argparse.Namespace) -> None:
    parameters: tuple[object, ...] = ()
    where = ""
    if args.platform_id is not None:
        platform = ensure_platform(db, args.platform_id)
        where = "WHERE i.platform_id = ?"
        parameters = (args.platform_id,)
        print(f"平台：{platform['name']}（ID {platform['id']}）")

    rows = db.execute(
        "SELECT i.id, i.platform_id, p.name AS platform_name, i.image_type, "
        "i.is_primary, i.sort_order, i.image_url, i.local_path, i.caption, "
        "i.source_name, i.source_url "
        "FROM platform_images AS i "
        "JOIN platforms AS p ON p.id = i.platform_id "
        f"{where} "
        "ORDER BY i.platform_id, i.is_primary DESC, i.sort_order, i.id",
        parameters,
    ).fetchall()

    if not rows:
        print("没有图片记录。")
        return

    print("ID\t平台ID\t主图\t顺序\t类型\t平台\t图片位置\t说明\t来源")
    for row in rows:
        location = row["image_url"] or row["local_path"] or "—"
        source = row["source_name"] or row["source_url"] or "—"
        print(
            "\t".join(
                (
                    str(row["id"]),
                    str(row["platform_id"]),
                    "是" if row["is_primary"] else "否",
                    str(row["sort_order"]),
                    row["image_type"],
                    row["platform_name"],
                    location,
                    row["caption"] or "—",
                    source,
                )
            )
        )


def command_add(db: sqlite3.Connection, args: argparse.Namespace) -> None:
    platform = ensure_platform(db, args.platform_id)
    image_url = (
        validate_http_url(args.image_url, "image-url")
        if args.image_url is not None
        else None
    )
    local_path = (
        validate_local_path(args.local_path) if args.local_path is not None else None
    )
    source_url = (
        validate_http_url(args.source_url, "source-url")
        if args.source_url is not None
        else None
    )
    caption = optional_text(args.caption)
    source_name = optional_text(args.source_name)

    try:
        with db:
            if args.primary:
                db.execute(
                    "UPDATE platform_images SET is_primary = 0 WHERE platform_id = ?",
                    (args.platform_id,),
                )
            cursor = db.execute(
                "INSERT INTO platform_images ("
                "platform_id, image_url, local_path, caption, source_url, source_name, "
                "image_type, is_primary, sort_order"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    args.platform_id,
                    image_url,
                    local_path,
                    caption,
                    source_url,
                    source_name,
                    args.image_type,
                    1 if args.primary else 0,
                    args.sort_order,
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise ImageManagerError(f"新增图片失败，数据未写入：{exc}") from exc

    print(
        f"已新增图片 ID {cursor.lastrowid}，平台：{platform['name']}（ID {platform['id']}）"
        + ("，并设为主图。" if args.primary else "。")
    )


def command_set_primary(db: sqlite3.Connection, args: argparse.Namespace) -> None:
    image = ensure_image(db, args.image_id)
    try:
        with db:
            # Both writes are committed or rolled back together. Clearing the old
            # primary first also satisfies the partial unique index.
            db.execute(
                "UPDATE platform_images SET is_primary = 0 WHERE platform_id = ?",
                (image["platform_id"],),
            )
            updated = db.execute(
                "UPDATE platform_images SET is_primary = 1 WHERE id = ?",
                (args.image_id,),
            )
            if updated.rowcount != 1:
                raise ImageManagerError(f"图片 ID {args.image_id} 在事务中已不存在。")
    except sqlite3.IntegrityError as exc:
        raise ImageManagerError(f"设置主图失败，原主图保持不变：{exc}") from exc

    print(f"图片 ID {args.image_id} 已设为平台 ID {image['platform_id']} 的主图。")


def command_delete(db: sqlite3.Connection, args: argparse.Namespace) -> None:
    image = ensure_image(db, args.image_id)
    with db:
        deleted = db.execute("DELETE FROM platform_images WHERE id = ?", (args.image_id,))
        if deleted.rowcount != 1:
            raise ImageManagerError(f"图片 ID {args.image_id} 在事务中已不存在。")
    suffix = "（原主图已删除；该平台目前没有主图）" if image["is_primary"] else ""
    print(f"已删除图片 ID {args.image_id}。{suffix}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="维护海上无人平台资料库中的图片记录",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite 数据库路径（默认：{DEFAULT_DB}）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出图片记录")
    list_parser.add_argument(
        "--platform-id", type=positive_id, help="仅列出指定平台的图片"
    )
    list_parser.set_defaults(handler=command_list)

    add_parser = subparsers.add_parser("add", help="新增一条图片记录")
    add_parser.add_argument("--platform-id", type=positive_id, required=True)
    location = add_parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--image-url", help="远程图片的完整 http(s) URL")
    location.add_argument(
        "--local-path", help="static 下的路径，必须位于 img/platforms/..."
    )
    add_parser.add_argument("--caption", help="图片说明")
    add_parser.add_argument("--source-url", help="图片来源页的完整 http(s) URL")
    add_parser.add_argument("--source-name", help="图片来源名称")
    add_parser.add_argument(
        "--image-type",
        choices=IMAGE_TYPES,
        default="other",
        help="图片类型（默认：other）",
    )
    add_parser.add_argument(
        "--sort-order", type=nonnegative_int, default=0, help="显示顺序（默认：0）"
    )
    add_parser.add_argument(
        "--primary", action="store_true", help="将新图片设为该平台主图"
    )
    add_parser.set_defaults(handler=command_add)

    primary_parser = subparsers.add_parser("set-primary", help="把现有图片设为主图")
    primary_parser.add_argument("image_id", type=positive_id, help="图片 ID")
    primary_parser.set_defaults(handler=command_set_primary)

    delete_parser = subparsers.add_parser("delete", help="删除一条图片记录")
    delete_parser.add_argument("image_id", type=positive_id, help="图片 ID")
    delete_parser.set_defaults(handler=command_delete)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db: sqlite3.Connection | None = None
    try:
        db = open_database(args.db)
        args.handler(db, args)
        return 0
    except ImageManagerError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except sqlite3.Error as exc:
        print(f"SQLite 错误：{exc}", file=sys.stderr)
        return 1
    finally:
        if db is not None:
            db.close()


if __name__ == "__main__":
    raise SystemExit(main())

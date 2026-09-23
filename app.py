"""Read-only digital catalogue for maritime uncrewed logistics/combat platforms."""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode, urlparse

from flask import Flask, abort, g, render_template, request, url_for


ROOT = Path(__file__).resolve().parent
PERFORMANCE = (
    ("length_text", "长度"),
    ("beam_draft_text", "宽度 / 吃水"),
    ("weight_displacement_text", "重量 / 排水量"),
    ("payload_text", "有效载荷"),
    ("speed_text", "速度"),
    ("range_text", "航程"),
    ("endurance_text", "续航"),
    ("propulsion_sea_text", "动力 / 海况"),
)
PERFORMANCE_GROUPS = (
    ("基本尺寸", PERFORMANCE[0:3]),
    ("运载性能", PERFORMANCE[3:4]),
    ("航行性能", PERFORMANCE[4:7]),
    ("动力与环境", PERFORMANCE[7:8]),
)
HIGHLIGHT_FIELDS = (
    ("length_text", "长度"),
    ("payload_text", "有效载荷"),
    ("speed_text", "速度"),
    ("range_text", "航程"),
    ("endurance_text", "续航"),
)
EVIDENCE_HELP = {
    "E2": "确认参演",
    "E3": "演习中执行任务",
    "E4": "实际军事部署",
    "E5": "公开实战使用",
}
UNRATED_EVIDENCE_FILTER = "unrated"
SOURCE_ROLE_LABELS = {
    "performance": "性能参数",
    "activity": "活动 / 试验 / 部署 / 实战",
    "control": "操控 / 人员参与",
}
MISSING_VALUES = {
    "未公开", "未给出", "未列出", "无公开资料", "未在该官方页面公开",
    "官方当前公开页未列",
}
CAPABILITY_TERMS = {
    "运输与保障": (
        ("食品/水", "食品 / 水"), ("燃料", "燃料"), ("弹药", "弹药运输"),
        ("医疗物资", "医疗物资"), ("维修件", "维修件"), ("零件", "零件"),
        ("车辆", "车辆"), ("货物", "货物"), ("补给", "海上补给"),
        ("Logistics", "Logistics"), ("运输", "运输"),
    ),
    "作战与任务载荷": (
        ("Surface Strike", "Surface Strike"), ("导弹", "导弹"),
        ("制导火箭", "制导火箭"), ("火箭", "火箭"), ("鱼雷", "鱼雷"),
        ("爆炸", "爆炸载荷"), ("战斗载荷", "战斗载荷"), ("武器", "武器系统"),
        ("ISR", "ISR"), ("声呐", "声呐"), ("MCM", "MCM"),
        ("拦截", "拦截"), ("设施保护", "设施保护"), ("母艇", "无人系统母艇"),
    ),
}


def is_missing(value) -> bool:
    if value is None or not str(value).strip():
        return True
    text = str(value).strip()
    # Only collapse a value that is entirely a missing-data marker. Longer
    # source text such as "高续航平台；具体天数未公开" still carries evidence.
    return text in MISSING_VALUES


def safe_http_url(value: str | None) -> str | None:
    if not value:
        return None
    url = value.strip()
    if any(character.isspace() or ord(character) < 32 for character in url):
        return None
    try:
        parsed = urlparse(url)
        _port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return url


def safe_static_path(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or normalized.startswith("/"):
        return None
    if normalized != "img/placeholder-platform.svg" and not normalized.startswith("img/platforms/"):
        return None
    return normalized


def capability_groups(text: str | None) -> list[dict]:
    source = text or ""
    groups = []
    for heading, terms in CAPABILITY_TERMS.items():
        labels = []
        for needle, label in terms:
            if needle.lower() in source.lower() and label not in labels:
                if needle == "火箭" and "制导火箭" in source:
                    continue
                labels.append(label)
        if labels:
            groups.append({"heading": heading, "items": labels})
    return groups


def activity_year(description: str) -> str:
    # Chinese characters are ``\w`` in Python, so ``\b`` does not delimit
    # a year followed by Chinese text (for example "2025测试").
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", description or "")
    return match.group(1) if match else "年份未注明"


def evidence_badge_label(code: str | None, raw: str | None) -> str:
    """Return a compact badge without promoting below-threshold evidence to E2."""
    if code in EVIDENCE_HELP:
        return code
    if re.search(r"未达\s*E2", raw or "", flags=re.IGNORECASE):
        return "未达E2"
    return "未评级"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config["DATABASE"] = os.environ.get("PLATFORM_DB", str(ROOT / "data" / "platforms.sqlite3"))
    if test_config:
        app.config.update(test_config)

    def get_db():
        if "db" not in g:
            db = sqlite3.connect(app.config["DATABASE"])
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            g.db = db
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.template_filter("shown")
    def shown(value):
        return "—" if is_missing(value) else str(value).strip()

    def image_record(row=None):
        placeholder = url_for("static", filename="img/placeholder-platform.svg")
        if row is None:
            return {
                "src": placeholder,
                "caption": "平台图片待补充（统一占位图）",
                "source_url": None,
                "source_name": None,
                "image_type": "other",
                "is_placeholder": True,
            }
        item = dict(row)
        remote = safe_http_url(item.get("image_url"))
        local = safe_static_path(item.get("local_path"))
        src = remote or (url_for("static", filename=local) if local else placeholder)
        return {
            **item,
            "src": src,
            "caption": item.get("caption") or "平台图片",
            "source_url": safe_http_url(item.get("source_url")),
            "is_placeholder": not (remote or local),
        }

    def platform_images(db, platform_id: int) -> list[dict]:
        table_exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='platform_images'"
        ).fetchone()
        if not table_exists:
            return [image_record()]
        rows = db.execute(
            "SELECT id, image_url, local_path, caption, source_url, source_name, image_type, "
            "is_primary, sort_order FROM platform_images WHERE platform_id = ? "
            "ORDER BY is_primary DESC, sort_order, id",
            (platform_id,),
        ).fetchall()
        cleaned = [image_record(row) for row in rows]
        return cleaned or [image_record()]

    def primary_images(db, platform_ids: list[int]) -> dict[int, dict]:
        """Fetch at most one ordered image per platform in a single query."""
        if not platform_ids:
            return {}
        table_exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='platform_images'"
        ).fetchone()
        if not table_exists:
            return {}
        placeholders = ",".join("?" for _ in platform_ids)
        rows = db.execute(
            "SELECT i.platform_id, i.id, i.image_url, i.local_path, i.caption, i.source_url, "
            "i.source_name, i.image_type, i.is_primary, i.sort_order FROM platform_images i "
            f"WHERE i.platform_id IN ({placeholders}) AND i.id = ("
            "SELECT i2.id FROM platform_images i2 WHERE i2.platform_id=i.platform_id "
            "ORDER BY i2.is_primary DESC, i2.sort_order, i2.id LIMIT 1)",
            platform_ids,
        ).fetchall()
        return {row["platform_id"]: image_record(row) for row in rows}

    def clean_links(rows) -> list[dict]:
        links = []
        for row in rows:
            item = dict(row)
            item["url"] = safe_http_url(item.get("url"))
            if item["url"]:
                item["role_label"] = SOURCE_ROLE_LABELS.get(item.get("role"), "参考资料")
                links.append(item)
        return links

    def query_url(**changes):
        values = {
            key: request.args.get(key, "").strip()
            for key in ("q", "country", "label", "batch", "evidence", "view")
        }
        values.update(changes)
        return url_for("index") + "?" + urlencode({k: v for k, v in values.items() if v})

    @app.context_processor
    def shared_context():
        return {
            "evidence_help": EVIDENCE_HELP,
            "evidence_badge_label": evidence_badge_label,
            "source_role_labels": SOURCE_ROLE_LABELS,
            "query_url": query_url,
        }

    @app.route("/")
    def index():
        db = get_db()
        filters = {
            "q": request.args.get("q", "").strip(),
            "country": request.args.get("country", "").strip(),
            "label": request.args.get("label", "").strip(),
            "batch": request.args.get("batch", "").strip(),
            "evidence": request.args.get("evidence", "").strip(),
        }
        view = request.args.get("view", "grid").strip().lower()
        if view not in {"grid", "list"}:
            view = "grid"

        clauses, parameters = [], []
        if filters["q"]:
            needle = filters["q"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{needle}%"
            clauses.append(
                "(p.name LIKE ? ESCAPE '\\' OR p.country LIKE ? ESCAPE '\\' "
                "OR p.platform_type LIKE ? ESCAPE '\\' OR p.payload_description LIKE ? ESCAPE '\\' "
                "OR EXISTS (SELECT 1 FROM activities a WHERE a.platform_id=p.id "
                "AND a.description LIKE ? ESCAPE '\\'))"
            )
            parameters.extend([pattern] * 5)
        if filters["country"]:
            clauses.append("p.country = ?")
            parameters.append(filters["country"])
        if filters["label"] in {"L", "L/W", "W"}:
            clauses.append("p.label = ?")
            parameters.append(filters["label"])
        if filters["batch"] in {"1", "2"}:
            clauses.append("p.batch = ?")
            parameters.append(int(filters["batch"]))
        if filters["evidence"] in EVIDENCE_HELP:
            clauses.append("p.evidence_code = ?")
            parameters.append(filters["evidence"])
        elif filters["evidence"] == UNRATED_EVIDENCE_FILTER:
            clauses.append("p.evidence_code IS NULL")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = db.execute(
            "SELECT p.*, (SELECT description FROM activities a WHERE a.platform_id=p.id "
            "ORDER BY sequence_no LIMIT 1) AS lead_activity FROM platforms p" + where + " ORDER BY p.batch, p.id",
            parameters,
        ).fetchall()
        platforms = []
        image_map = primary_images(db, [row["id"] for row in rows])
        spec_candidates = (
            ("payload_text", "有效载荷"), ("speed_text", "速度"),
            ("range_text", "航程"), ("endurance_text", "续航"),
            ("length_text", "长度"), ("weight_displacement_text", "重量 / 排水量"),
            ("beam_draft_text", "宽度 / 吃水"), ("propulsion_sea_text", "动力 / 海况"),
        )
        for row in rows:
            item = dict(row)
            item["primary_image"] = image_map.get(item["id"], image_record())
            meaningful = [pair for pair in spec_candidates if not is_missing(item.get(pair[0]))]
            remaining = [pair for pair in spec_candidates if pair not in meaningful]
            item["key_specs"] = [
                {"label": label, "value": item.get(field)}
                for field, label in (meaningful + remaining)[:4]
            ]
            platforms.append(item)

        countries = [row[0] for row in db.execute("SELECT DISTINCT country FROM platforms ORDER BY country")]
        counts = {
            "total": db.execute("SELECT COUNT(*) FROM platforms").fetchone()[0],
            "countries": db.execute("SELECT COUNT(DISTINCT country) FROM platforms").fetchone()[0],
            "activities": db.execute("SELECT COUNT(*) FROM activities").fetchone()[0],
        }
        active_filters = sum(bool(value) for value in filters.values())
        return render_template(
            "index.html", platforms=platforms, filters=filters, countries=countries, counts=counts,
            view=view, active_filters=active_filters,
        )

    @app.route("/platform/<int:platform_id>")
    def detail(platform_id):
        db = get_db()
        row = db.execute("SELECT * FROM platforms WHERE id = ?", (platform_id,)).fetchone()
        if row is None:
            abort(404)
        platform = dict(row)
        activities = [
            {**dict(item), "year": activity_year(item["description"])}
            for item in db.execute(
                "SELECT id, sequence_no, description FROM activities WHERE platform_id = ? ORDER BY sequence_no",
                (platform_id,),
            ).fetchall()
        ]
        links = clean_links(db.execute(
            "SELECT role, title, url FROM source_links WHERE platform_id = ? "
            "ORDER BY CASE role WHEN 'performance' THEN 1 WHEN 'activity' THEN 2 ELSE 3 END, id",
            (platform_id,),
        ).fetchall())
        links_by_role = {role: [link for link in links if link["role"] == role] for role in SOURCE_ROLE_LABELS}
        return render_template(
            "platform_detail.html", platform=platform, activities=activities, links=links,
            links_by_role=links_by_role, images=platform_images(db, platform_id),
            performance_groups=PERFORMANCE_GROUPS, highlight_fields=HIGHLIGHT_FIELDS,
            capability_groups=capability_groups(platform.get("payload_description")),
        )

    @app.route("/compare")
    def compare():
        raw = request.args.get("ids", "").strip()
        ids = []
        if raw:
            for token in raw.split(","):
                token = token.strip()
                if not re.fullmatch(r"[1-9]\d{0,18}", token):
                    abort(400)
                value = int(token)
                if value not in ids:
                    ids.append(value)
        if len(ids) > 4:
            abort(400)
        db = get_db()
        platforms = []
        if ids:
            placeholders = ",".join("?" for _ in ids)
            rows = db.execute(f"SELECT * FROM platforms WHERE id IN ({placeholders})", ids).fetchall()
            by_id = {row["id"]: dict(row) for row in rows}
            for platform_id in ids:
                if platform_id not in by_id:
                    continue
                item = by_id[platform_id]
                item["primary_image"] = platform_images(db, platform_id)[0]
                item["performance_sources"] = clean_links(db.execute(
                    "SELECT role, title, url FROM source_links WHERE platform_id=? AND role='performance' ORDER BY id",
                    (platform_id,),
                ).fetchall())
                platforms.append(item)
        comparison_selection = [
            {"id": item["id"], "name": item["name"], "country": item["country"]}
            for item in platforms
        ]
        return render_template(
            "compare.html", platforms=platforms, requested_ids=ids, performance=PERFORMANCE,
            comparison_selection=comparison_selection,
        )

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.errorhandler(400)
    @app.errorhandler(404)
    def error_page(error):
        return render_template("error.html", error=error), error.code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

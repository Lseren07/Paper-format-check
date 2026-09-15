import json
from pathlib import Path
from typing import Any

from .contracts import RuleSet


def _read_source(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    if isinstance(source, Path) or (isinstance(source, str) and Path(source).exists()):
        return json.loads(Path(source).read_text(encoding="utf-8"))
    if isinstance(source, str):
        return json.loads(source)
    raise TypeError("rules source must be a path, JSON string, or mapping")


def _pt_to_char_indent(indent_pt: Any, size_pt: Any) -> str | None:
    """把磅值缩进换算成「N字符」，与 default.json 的写法保持一致。"""
    try:
        characters = float(indent_pt) / float(size_pt)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if characters <= 0 or abs(characters - round(characters)) > 0.01:
        return None
    return f"{int(round(characters))}字符"


def _flat_checks(prefix: str, target: str, raw_config: dict[str, Any]) -> list[dict[str, Any]]:
    """把 `{font, size, alignment, bold, ...}` 的平铺配置展开成检查项。"""
    checks: list[dict[str, Any]] = []
    # 兼容更早的写法：size / line_spacing / first_line_indent 不带 _pt 后缀。
    config = dict(raw_config)
    for plain, pt_key in (("size", "size_pt"), ("line_spacing", "line_spacing_pt"), ("first_line_indent", "first_line_indent_pt")):
        if plain in config and pt_key not in config:
            config[pt_key] = config[plain]
    if config.get("font"):
        checks.append({"id": f"{prefix}-font", "type": "font", "target": target, "expected": {"font": config["font"]}})
    if config.get("size_pt") is not None:
        checks.append({"id": f"{prefix}-size", "type": "size", "target": target, "expected": {"size": config["size_pt"]}})
    if config.get("alignment"):
        checks.append({"id": f"{prefix}-alignment", "type": "alignment", "target": target, "expected": {"alignment": config["alignment"]}})
    if config.get("bold") is not None:
        checks.append({"id": f"{prefix}-bold", "type": "bold", "target": target, "expected": {"bold": config["bold"]}})
    if config.get("line_spacing_pt") is not None:
        checks.append({"id": f"{prefix}-line-spacing", "type": "line_spacing", "target": target, "expected": {"line_spacing": config["line_spacing_pt"]}})
    if config.get("first_line_indent_pt") is not None:
        indent = _pt_to_char_indent(config["first_line_indent_pt"], config.get("size_pt")) or config["first_line_indent_pt"]
        key = "first_line_indent" if isinstance(indent, str) else "first_line_indent_pt"
        checks.append({"id": f"{prefix}-first-line-indent", "type": "paragraph_indent", "target": target, "expected": {key: indent}})
    spacing = {key: config[key] for key in ("space_before_pt", "space_after_pt") if config.get(key) is not None}
    if spacing:
        checks.append({"id": f"{prefix}-spacing", "type": "paragraph_spacing", "target": target, "expected": spacing})
    return checks


def _page_check(page: dict[str, Any]) -> dict[str, Any] | None:
    """旧版结构的 `page` 段（纸张与页边距）→ 一条 page_margin 检查。"""
    expected: dict[str, Any] = {}
    margins = page.get("margins_cm") or {}
    if margins:
        expected["margin"] = {side: f"{value}cm" for side, value in margins.items()}
    size = {key: page[key] for key in ("width_cm", "height_cm") if page.get(key) is not None}
    if size:
        expected["page"] = size
    for key, name in (("header_distance_cm", "header"), ("footer_distance_cm", "footer")):
        if page.get(key) is not None:
            expected[name] = f"{page[key]}cm"
    if not expected:
        return None
    return {"id": "page-margin", "type": "page_margin", "target": "all", "expected": expected}


def _legacy_to_checks(data: dict[str, Any]) -> dict[str, Any]:
    if "checks" in data:
        return data

    checks: list[dict[str, Any]] = []
    page_check = _page_check(data.get("page") or {})
    if page_check:
        checks.append(page_check)

    body = data.get("body") or {}
    checks.extend(_flat_checks("body", "body", body))

    # 标题：优先新版 `headings: {"1": {...}}`，回退旧版平铺的 title1 / title2。
    headings = data.get("headings") or {}
    for level, config in headings.items():
        checks.extend(_flat_checks(f"title{level}", f"title{level}", config or {}))
    for title_name in ("title1", "title2"):
        config = data.get(title_name) or {}
        for key, rule_type in (("font", "font"), ("size", "size"), ("alignment", "alignment"), ("bold", "bold")):
            if key in config:
                checks.append({"id": f"{title_name}-{key}", "type": rule_type, "target": title_name, "expected": {key: config[key]}})

    legacy: dict[str, Any] = {
        "schema_version": data.get("schema_version", "1.0"),
        "name": data.get("name", "rules"),
        "checks": checks,
    }
    for key in ("rule_set_id", "description"):
        if data.get(key):
            legacy[key] = data[key]

    manual = [item for item in (data.get("manual_checks") or []) if isinstance(item, str) and item.strip()]
    source = data.get("source")
    if source is not None or manual:
        legacy["source"] = _legacy_source(data, manual)
    return legacy


def _legacy_source(data: dict[str, Any], manual: list[str]) -> dict[str, Any]:
    """构造旧结构规则文件的来源说明：`manual_checks` 落成人工核对提示。

    只搬运文件里已有的内容，不补写任何规范条款。
    """
    raw = data.get("source")
    source: dict[str, Any] = raw if isinstance(raw, dict) else {
        "title": data.get("name") or "未命名规则集",
        "document": str(raw) if raw else "",
    }
    if manual:
        notes = list(source.get("notes") or [])
        notes.extend(item for item in manual if item not in notes)
        source = {**source, "notes": notes}
    return source


def _normalize_source(data: dict[str, Any]) -> dict[str, Any]:
    """兼容 `source` 为纯文件名字符串的旧写法，统一成对象形态。"""
    raw = data.get("source")
    if not isinstance(raw, str):
        return data
    normalized = dict(data)
    normalized["source"] = {"title": data.get("name") or Path(raw).stem, "document": raw}
    return normalized


def load_rules(source: str | Path | dict[str, Any]) -> RuleSet:
    data = _normalize_source(_legacy_to_checks(_read_source(source)))
    data.pop("$schema", None)
    return RuleSet.model_validate(data)

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


def _legacy_to_checks(data: dict[str, Any]) -> dict[str, Any]:
    if "checks" in data:
        return data
    checks: list[dict[str, Any]] = []
    body = data.get("body", {})
    mapping = {
        "font": ("font", body.get("font")),
        "size": ("size", body.get("size")),
        "line_spacing": ("line_spacing", body.get("line_spacing")),
        "first_line_indent": ("paragraph_indent", body.get("first_line_indent")),
        "alignment": ("alignment", body.get("alignment")),
    }
    for key, (rule_type, value) in mapping.items():
        if value is not None:
            checks.append({"id": f"body-{key}", "type": rule_type, "target": "body", "expected": {key: value}})
    for title_name, title in (("title1", data.get("title1", {})), ("title2", data.get("title2", {}))):
        for key, rule_type in (("font", "font"), ("size", "size"), ("alignment", "alignment"), ("bold", "bold")):
            if key in title:
                checks.append({"id": f"{title_name}-{key}", "type": rule_type, "target": title_name, "expected": {key: title[key]}})
    return {"schema_version": data.get("schema_version", "1.0"), "name": data.get("name", "rules"), "checks": checks}


def load_rules(source: str | Path | dict[str, Any]) -> RuleSet:
    data = _legacy_to_checks(_read_source(source))
    data.pop("$schema", None)
    return RuleSet.model_validate(data)

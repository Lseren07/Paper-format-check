"""Load and validate local paper-format rule sets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {"schema_version", "rule_set_id", "page", "body", "headings"}
REQUIRED_RULE_FIELDS = {
    "page": (
        "width_cm",
        "height_cm",
        "margins_cm.top",
        "margins_cm.right",
        "margins_cm.bottom",
        "margins_cm.left",
        "header_distance_cm",
        "footer_distance_cm",
    ),
    "body": (
        "font",
        "size_pt",
        "alignment",
        "first_line_indent_pt",
        "line_spacing_rule",
        "line_spacing_pt",
        "space_before_pt",
        "space_after_pt",
    ),
}


def load_rules(path: str | Path) -> dict[str, Any]:
    rule_path = Path(path)
    with rule_path.open("r", encoding="utf-8") as stream:
        rules = json.load(stream)
    if not isinstance(rules, dict):
        raise ValueError("Rule set must be a JSON object")
    missing = REQUIRED_TOP_LEVEL_KEYS - rules.keys()
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"Rule set is missing required keys: {missing_text}")
    for group, fields in REQUIRED_RULE_FIELDS.items():
        values = rules[group]
        if not isinstance(values, dict):
            raise ValueError(f"Rule group must be an object: {group}")
        for field in fields:
            current: Any = values
            for part in field.split("."):
                if not isinstance(current, dict) or part not in current:
                    raise ValueError(f"Rule set is missing required field: {group}.{field}")
                current = current[part]
    if not isinstance(rules["headings"], dict):
        raise ValueError("Rule group must be an object: headings")
    return rules

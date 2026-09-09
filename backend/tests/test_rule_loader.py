import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.rules.loader import load_rules
from backend.app.rules.contracts import CheckRule


def test_load_rules_accepts_stage2_schema(tmp_path: Path) -> None:
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "name": "test",
        "checks": [{"id": "body-font", "type": "font", "target": "body", "expected": {"font": "宋体"}}],
    }), encoding="utf-8")
    rules = load_rules(path)
    assert rules.checks[0].expected["font"] == "宋体"


def test_load_rules_rejects_missing_check_identity() -> None:
    with pytest.raises(ValidationError):
        load_rules({"schema_version": "1.0", "name": "test", "checks": [{"expected": {}}]})


def test_load_legacy_default_rule_file_maps_flat_fields() -> None:
    rules = load_rules(Path(__file__).parents[2] / "rules" / "default.json")
    assert any(check.type == "font" for check in rules.checks)


def test_rule_target_rejects_unknown_name_and_invalid_heading_level() -> None:
    with pytest.raises(ValidationError):
        CheckRule(id="x", type="font", target={"name": "unknown"}, expected={})
    with pytest.raises(ValidationError):
        CheckRule(id="x", type="font", target={"name": "heading", "heading_level": 0}, expected={})

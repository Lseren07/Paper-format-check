import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.rules.loader import load_rules
from backend.app.rules.contracts import CheckRule


DEFAULT_RULES = Path(__file__).parents[2] / "rules" / "default.json"


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
    rules = load_rules(DEFAULT_RULES)
    assert any(check.type == "font" for check in rules.checks)


def test_default_rule_file_keeps_chinese_expected_values() -> None:
    rules = load_rules(DEFAULT_RULES)
    expected = {check.id: check.expected for check in rules.checks}
    assert expected["body-font"]["font"] == "宋体"
    assert expected["body-size"]["size"] == "小四"
    assert expected["body-first-line-indent"]["first_line_indent"] == "2字符"
    assert expected["title1-font"]["font"] == "黑体"
    assert expected["title1-size"]["size"] == "三号"
    assert expected["title2-font"]["font"] == "黑体"
    assert expected["title2-size"]["size"] == "四号"


def test_legacy_service_loader_uses_stage2_rule_contract() -> None:
    from backend.app.services.rules import load_rules as legacy_load_rules

    rules = legacy_load_rules(DEFAULT_RULES)

    assert rules.model_dump() == load_rules(DEFAULT_RULES).model_dump()


def test_rule_target_rejects_unknown_name_and_invalid_heading_level() -> None:
    with pytest.raises(ValidationError):
        CheckRule(id="x", type="font", target={"name": "unknown"}, expected={})
    with pytest.raises(ValidationError):
        CheckRule(id="x", type="font", target={"name": "heading", "heading_level": 0}, expected={})

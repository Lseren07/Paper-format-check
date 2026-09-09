import pytest

from backend.app.models.contracts import Document
from backend.app.rules.contracts import CheckRule, RuleSet
from backend.app.rules.engine import RuleEngine
from backend.app.rules.errors import make_error


def test_engine_skips_disabled_rules_and_keeps_stable_error_ids() -> None:
    document = Document(document_id="D1", source_filename="x.docx")
    rules = RuleSet(schema_version="1.0", name="x", checks=[
        CheckRule(id="disabled", type="font", target="body", enabled=False, expected={}),
    ])
    assert RuleEngine(document, rules).run() == []


def test_error_factory_uses_frozen_error_contract() -> None:
    rule = CheckRule(id="body-font", type="font", target="body", expected={})
    error = make_error(rule, location="p-0001", content="正文", current="黑体", expected="宋体")
    assert error.error_id == "body-font:p-0001"
    assert "required" not in error.model_dump()


def test_engine_rejects_unknown_enabled_rule_type() -> None:
    rules = RuleSet(schema_version="1.0", name="x", checks=[CheckRule(id="x", type="unknown", expected={})])
    with pytest.raises(ValueError, match="unknown"):
        RuleEngine(Document(document_id="D1", source_filename="x.docx"), rules).run()

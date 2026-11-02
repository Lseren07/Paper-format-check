"""规则元数据契约：/rule/list 与 /rule/{id} 必须给出完整的规范来源。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.rules.registry import clear_rule_cache, discover_rule_sets, resolve_rule_set

REPO_RULES = Path(__file__).parents[2] / "rules"
DEFAULT_SOURCE = json.loads((REPO_RULES / "default.json").read_text(encoding="utf-8"))["source"]


def test_rule_list_exposes_source_organization_and_scope() -> None:
    body = TestClient(app).get("/api/v1/rule/list").json()

    assert body["code"] == 200
    rule_sets = {item["id"]: item for item in body["data"]["rule_sets"]}
    default = rule_sets["default"]

    assert default["source_title"] == DEFAULT_SOURCE["title"]
    assert default["source_document"] == DEFAULT_SOURCE["document"]
    assert default["source_organization"] == DEFAULT_SOURCE["organization"]
    assert default["source_scope"] == DEFAULT_SOURCE["scope"]
    assert default["source_clause_count"] == len(DEFAULT_SOURCE["clauses"])


def test_source_clause_count_matches_rule_file() -> None:
    """条款数必须来自规则文件本身，不能写死。"""
    info = resolve_rule_set("default").info

    assert info.source_clause_count == len(DEFAULT_SOURCE["clauses"])
    assert info.source_clause_count > 0


def test_rule_detail_exposes_source_summary() -> None:
    data = TestClient(app).get("/api/v1/rule/default").json()["data"]

    assert data["source"] == {
        "title": DEFAULT_SOURCE["title"],
        "document": DEFAULT_SOURCE["document"],
        "organization": DEFAULT_SOURCE["organization"],
        "scope": DEFAULT_SOURCE["scope"],
        "clause_count": len(DEFAULT_SOURCE["clauses"]),
    }


def test_default_rule_set_id_stays_stable() -> None:
    """规则集 id 回退到文件名，本轮不能变。"""
    clear_rule_cache()

    ids = {info.id for info in discover_rule_sets()}

    assert "default" in ids
    assert resolve_rule_set("default").info.file == "default.json"


def test_rule_set_without_source_reports_zero_clauses(tmp_path, monkeypatch) -> None:
    """没有 source 的规则集不伪造来源：字段为空、条款数为 0。"""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    payload = {
        "schema_version": "1.0",
        "name": "无来源规则集",
        "checks": [{"id": "body-font", "type": "font", "target": "body", "expected": {"font": "宋体"}}],
    }
    (rules_dir / "no-source.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("PAPER_RULES_DIR", str(rules_dir))
    clear_rule_cache()
    try:
        client = TestClient(app)
        item = next(
            entry for entry in client.get("/api/v1/rule/list").json()["data"]["rule_sets"] if entry["id"] == "no-source"
        )
        assert item["source_available"] is False
        assert item["source_organization"] is None
        assert item["source_scope"] is None
        assert item["source_clause_count"] == 0

        detail = client.get("/api/v1/rule/no-source").json()["data"]
        assert detail["source"] is None
    finally:
        clear_rule_cache()

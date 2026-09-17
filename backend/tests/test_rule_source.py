"""PDF 报告必须写真实的规范依据（rules.source），不能是占位文案。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.models.contracts import Document, ErrorItem
from backend.app.rules.loader import load_rules
from backend.app.rules.service import check_document
from backend.app.services import report as report_service
from backend.app.services.rule_summary import (
    clauses_by_rule_id,
    rule_basis_text,
    summarize_rule_source,
    unmapped_rule_ids,
)
from backend.app.services.task_store import TaskRecord, store

RULES = Path("rules/default.json")
PLACEHOLDER = "当前报告依据项目实际加载的规则文件生成"


def error(**overrides) -> ErrorItem:
    payload = {
        "error_id": "e1",
        "type": "font_error",
        "location": "第1段",
        "content": "正文示例",
        "current": "Calibri",
        "expected": "宋体",
        "rule_id": "body-font",
        "basis": "规则 body-font：font=宋体",
    }
    payload.update(overrides)
    return ErrorItem(**payload)


def test_default_rules_carry_source_metadata() -> None:
    rules = load_rules(RULES)
    assert rules.source is not None
    assert "成都学院" in rules.source.title
    assert rules.source.document.endswith("撰写格式规范.docx")
    assert rules.source.organization == "电子科技大学成都学院"
    assert rules.source.clauses and rules.source.notes


def test_every_enabled_rule_maps_to_exactly_one_clause() -> None:
    rules = load_rules(RULES)
    assert unmapped_rule_ids(rules) == []

    seen: dict[str, str] = {}
    for clause in rules.source.clauses:
        for rule_id in clause.rules:
            assert rule_id not in seen, f"规则 {rule_id} 被 {seen[rule_id]} 与 {clause.id} 重复引用"
            seen[rule_id] = clause.id


def test_manual_clauses_do_not_claim_automated_rules() -> None:
    summary = summarize_rule_source(load_rules(RULES))
    assert summary["available"] is True
    for clause in summary["clauses"]:
        if clause["automated"]:
            assert clause["rule_count"] > 0
        else:
            assert clause["rule_count"] == 0
    automated_total = sum(clause["rule_count"] for clause in summary["clauses"])
    assert automated_total == summary["check_count"]


def test_clause_rules_reference_real_checks() -> None:
    rules = load_rules(RULES)
    known = {check.id for check in rules.checks}
    for clause in rules.source.clauses:
        for rule_id in clause.rules:
            assert rule_id in known, f"条款 {clause.id} 引用了不存在的规则 {rule_id}"


def test_legacy_string_source_is_normalized() -> None:
    """旧写法（source 只写一个文件名）仍能加载，只是没有条款明细。"""
    rules = load_rules({
        "schema_version": "1.0",
        "name": "旧写法规则集",
        "source": "附件1：电子科技大学成都学院毕业论文（设计）撰写格式规范.docx",
        "checks": [],
    })
    assert rules.source is not None
    assert rules.source.document.endswith(".docx")
    assert rules.source.title == "旧写法规则集"
    assert summarize_rule_source(rules)["clauses"] == []


def test_source_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        load_rules({"schema_version": "1.0", "name": "x", "checks": [], "source": {"oops": 1}})


def test_summary_without_source_does_not_fake_basis() -> None:
    rules = load_rules({"schema_version": "1.0", "name": "无来源规则集", "checks": []})
    summary = summarize_rule_source(rules)
    assert summary["available"] is False
    assert "著录规范" not in rule_basis_text(rules)


def _story_text(task: TaskRecord) -> str:
    rules = load_rules(RULES)
    font_name = report_service.ensure_report_font()
    styles = report_service._styles(font_name)
    story = report_service.build_report_story(
        task, rules=rules, rule_file=RULES.name, styles=styles, font_name=font_name
    )
    parts = [item.text for item in story if hasattr(item, "text")]
    for item in story:
        rows = getattr(item, "_cellvalues", None)
        if rows:
            parts.extend(cell.text for row in rows for cell in row)
    return "\n".join(parts)


def test_report_results_come_first_and_basis_is_name_only() -> None:
    task = TaskRecord(task_id="Tbasis", filename="论文.docx", status="completed", errors=[error()])
    text = _story_text(task)
    source = load_rules(RULES).source

    assert PLACEHOLDER not in text
    assert source.title in text
    # 检测结果章节在检测依据章节之前，便于先看到错误
    assert text.index("检测结果") < text.index("检测依据")
    # 检测依据只保留规范名称，不再有条款明细表与人工核对提示
    assert "校验方式" not in text
    assert "自动（" not in text
    assert "人工核对" not in text
    assert "出处章节" not in text
    assert "规范摘要" not in text


def test_report_marks_each_error_with_its_clause() -> None:
    rules = load_rules(RULES)
    mapping = clauses_by_rule_id(rules)
    body_clause = mapping["body-font"]["title"]
    keyword_clause = mapping["keywords-zh"]["title"]

    text = _story_text(TaskRecord(
        task_id="Tclause",
        filename="论文.docx",
        status="completed",
        errors=[error(), error(error_id="e2", type="keyword_format_error", rule_id="keywords-zh", location="关键词段落")],
    ))

    assert body_clause in text
    assert keyword_clause in text
    assert "字体" in text  # 类型列已本地化，不再是 font_error


def test_report_without_errors_still_states_basis() -> None:
    text = _story_text(TaskRecord(task_id="Tclean", filename="论文.docx", status="completed"))
    assert PLACEHOLDER not in text
    assert "未发现格式问题" in text
    assert "成都学院" in text
    # 无错误时结果章节同样在依据之前
    assert text.index("检测结果") < text.index("检测依据")


def test_create_report_response_exposes_rule_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_service, "REPORT_DIR", tmp_path)
    store.put(TaskRecord(task_id="Tsource", filename="论文.docx", status="completed"))
    try:
        response = TestClient(app).post("/api/v1/report/create", json={"task_id": "Tsource"})
        assert response.status_code == 200
        source = response.json()["data"]["rule_source"]
        rules = load_rules(RULES)
        assert source["available"] is True
        assert "成都学院" in source["title"]
        assert source["document"].endswith(".docx")
        assert source["clause_count"] == len(rules.source.clauses)
        assert source["automated_clause_count"] + source["manual_clause_count"] == source["clause_count"]
        assert source["check_count"] == sum(1 for check in rules.checks if check.enabled)
    finally:
        store.delete("Tsource")


def test_report_clause_covers_errors_from_default_rules() -> None:
    """真实检测出来的错误，规则 id 必须在条款里找得到出处。"""
    rules = load_rules(RULES)
    errors = [
        item
        for item in check_document(Document(document_id="Dsource", source_filename="empty.docx"), RULES)
        if item.rule_id
    ]
    if not errors:
        pytest.skip("空文档在当前规则下没有可定位的错误")
    mapping = clauses_by_rule_id(rules)
    assert all(error.rule_id in mapping for error in errors)

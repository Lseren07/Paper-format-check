"""检测结果契约：stats / rule_source / rule_set_name 与失败 message。"""

import json
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from fastapi.testclient import TestClient

from backend.app.api import detect, upload
from backend.app.main import app
from backend.app.parser.errors import DocumentParseError
from backend.app.rules.registry import resolve_rule_set
from backend.app.services.task_store import TaskRecord, store

REPO_RULES = Path(__file__).parents[2] / "rules"
DEFAULT_SOURCE = json.loads((REPO_RULES / "default.json").read_text(encoding="utf-8"))["source"]


def make_docx() -> bytes:
    """正文用黑体，必然与默认规则（宋体）冲突，保证有错误项。"""
    document = Document()
    document.add_paragraph("第二章 系统设计", style="Heading 1")
    paragraph = document.add_paragraph()
    run = paragraph.add_run("随着人工智能技术的发展")
    run.font.name = "黑体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _prepare(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(upload, "UPLOAD_DIR", uploads)
    return TestClient(app)


def _detect(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/paper/upload",
        files={"file": ("thesis.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    task_id = response.json()["data"]["task_id"]
    started = client.post("/api/v1/detect/start", json={"task_id": task_id})
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "completed"
    return client.get(f"/api/v1/detect/result/{task_id}").json()["data"]


def test_result_stats_follow_contract_counting(tmp_path, monkeypatch) -> None:
    client = _prepare(tmp_path, monkeypatch)
    data = _detect(client)

    enabled = sum(1 for check in resolve_rule_set("default").rules.checks if check.enabled)
    issue_rule_ids = {error["rule_id"] for error in data["errors"] if error["rule_id"]}

    assert data["stats"]["rule_count"] == enabled
    assert data["stats"]["issue_rule_count"] == len(issue_rule_ids)
    assert data["stats"]["error_count"] == len(data["errors"])
    assert data["total_error"] == data["stats"]["error_count"]
    assert data["stats"]["rule_count"] >= data["stats"]["issue_rule_count"] >= 0


def test_result_exposes_rule_set_name_and_rule_source(tmp_path, monkeypatch) -> None:
    client = _prepare(tmp_path, monkeypatch)
    data = _detect(client)

    assert data["rule_set_name"] == "电子科技大学成都学院本科毕业论文格式规范"
    assert data["rule_source"] == {
        "title": DEFAULT_SOURCE["title"],
        "document": DEFAULT_SOURCE["document"],
        "organization": DEFAULT_SOURCE["organization"],
        "scope": DEFAULT_SOURCE["scope"],
        "clause_count": len(DEFAULT_SOURCE["clauses"]),
    }


def test_result_without_errors_reports_zero_issue_rules(tmp_path, monkeypatch) -> None:
    client = _prepare(tmp_path, monkeypatch)
    task = store.put(TaskRecord(task_id="Tclean000000", filename="clean.docx", status="completed", rule_set_id="default"))
    try:
        data = client.get("/api/v1/detect/result/Tclean000000").json()["data"]
    finally:
        store.delete(task.task_id)

    enabled = sum(1 for check in resolve_rule_set("default").rules.checks if check.enabled)
    assert data["status"] == "completed"
    assert data["errors"] == []
    assert data["stats"] == {"rule_count": enabled, "issue_rule_count": 0, "error_count": 0}
    assert data["rule_source"]["clause_count"] == len(DEFAULT_SOURCE["clauses"])


def test_detect_start_failure_returns_readable_message(tmp_path, monkeypatch) -> None:
    client = _prepare(tmp_path, monkeypatch)

    def boom(*args, **kwargs):
        raise DocumentParseError("invalid_docx", "文件不是有效的 DOCX 文档")

    monkeypatch.setattr(detect, "run_detection", boom)
    response = client.post(
        "/api/v1/paper/upload",
        files={"file": ("broken.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    task_id = response.json()["data"]["task_id"]

    body = client.post("/api/v1/detect/start", json={"task_id": task_id}).json()

    assert body["code"] == 200
    assert body["data"]["status"] == "failed"
    assert body["data"]["message"]
    assert "文件不是有效的 DOCX 文档" in body["data"]["message"]
    assert "未加密" in body["data"]["message"]
    # 失败任务不返回 stats，直接 400，与契约 §7.6 一致
    assert client.get(f"/api/v1/detect/result/{task_id}").status_code == 400
    store.delete(task_id)


def test_result_with_missing_rule_set_does_not_fake_counts(tmp_path, monkeypatch) -> None:
    """规则集被删后结果仍可取，但规则总数与来源不编造。"""
    client = _prepare(tmp_path, monkeypatch)
    task = store.put(TaskRecord(task_id="Tgone0000000", filename="gone.docx", status="completed", rule_set_id="deleted-school"))
    try:
        data = client.get("/api/v1/detect/result/Tgone0000000").json()["data"]
    finally:
        store.delete(task.task_id)

    assert data["stats"]["rule_count"] == 0
    assert data["stats"]["error_count"] == 0
    assert data["rule_set_name"] is None
    assert data["rule_source"] is None

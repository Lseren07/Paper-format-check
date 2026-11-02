"""报告字体可配置：不写死 Windows 路径，缺失时只影响报告。"""

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.app.api import upload
from backend.app.main import app
from backend.app.services import report as report_service
from backend.app.services.task_store import store


def test_env_font_path_wins(monkeypatch, tmp_path) -> None:
    custom = tmp_path / "custom.ttf"
    custom.write_bytes(b"fake")
    monkeypatch.setenv("REPORT_FONT_PATH", str(custom))

    assert report_service.report_font_path() == custom


def test_falls_back_to_platform_candidate(monkeypatch) -> None:
    monkeypatch.delenv("REPORT_FONT_PATH", raising=False)

    path = report_service.report_font_path()

    assert path.is_file()
    assert path.suffix.lower() in {".ttf", ".ttc"}


def test_missing_font_raises_readable_error(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REPORT_FONT_PATH", str(tmp_path / "nope.ttf"))
    monkeypatch.setattr(report_service, "REPORT_FONT_CANDIDATES", ())

    with pytest.raises(RuntimeError, match="REPORT_FONT_PATH"):
        report_service.report_font_path()


def test_report_failure_does_not_break_detection(monkeypatch, tmp_path) -> None:
    """字体缺失时报告 500，但检测结果照常可取。"""
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(upload, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(report_service, "REPORT_DIR", tmp_path / "reports")

    def no_font() -> Path:
        raise RuntimeError("中文 PDF 字体不存在，请设置 REPORT_FONT_PATH")

    monkeypatch.setattr(report_service, "ensure_report_font", no_font)
    client = TestClient(app)

    document = Document()
    document.add_paragraph("正文")
    stream = BytesIO()
    document.save(stream)
    uploaded = client.post(
        "/api/v1/paper/upload",
        files={"file": ("thesis.docx", stream.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    task_id = uploaded.json()["data"]["task_id"]
    assert client.post("/api/v1/detect/start", json={"task_id": task_id}).status_code == 200

    created = client.post("/api/v1/report/create", json={"task_id": task_id})
    assert created.status_code == 500
    assert created.json()["detail"] == "检测报告生成失败"

    result = client.get(f"/api/v1/detect/result/{task_id}")
    assert result.status_code == 200
    assert result.json()["data"]["status"] == "completed"
    store.delete(task_id)

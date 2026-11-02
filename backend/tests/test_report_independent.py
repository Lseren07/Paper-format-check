"""报告下载与内存任务解耦：引擎重启后已生成的 PDF 仍可取。"""

import json
from io import BytesIO
from urllib.parse import quote

from docx import Document
from fastapi.testclient import TestClient

from backend.app.api import upload
from backend.app.main import app
from backend.app.services import report as report_service
from backend.app.services.task_store import store


def make_docx() -> bytes:
    document = Document()
    document.add_paragraph("正文")
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _create_report(tmp_path, monkeypatch) -> tuple[TestClient, str, str]:
    upload_dir = tmp_path / "uploads"
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(upload, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(report_service, "REPORT_DIR", report_dir)
    client = TestClient(app)

    uploaded = client.post(
        "/api/v1/paper/upload",
        files={"file": ("毕业论文.docx", make_docx(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    task_id = uploaded.json()["data"]["task_id"]
    assert client.post("/api/v1/detect/start", json={"task_id": task_id}).status_code == 200
    created = client.post("/api/v1/report/create", json={"task_id": task_id})
    assert created.status_code == 200
    return client, task_id, created.json()["data"]["report_id"]


def test_download_survives_engine_restart(tmp_path, monkeypatch) -> None:
    """内存任务被清空（等价于进程重启）后，报告仍然可下载。"""
    client, task_id, report_id = _create_report(tmp_path, monkeypatch)

    store.delete(task_id)

    downloaded = client.get(f"/api/v1/report/download/{report_id}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert downloaded.content.startswith(b"%PDF")


def test_sidecar_records_report_metadata(tmp_path, monkeypatch) -> None:
    _client, task_id, report_id = _create_report(tmp_path, monkeypatch)

    meta = json.loads((tmp_path / "reports" / f"{report_id}.json").read_text(encoding="utf-8"))

    assert meta["report_id"] == report_id
    assert meta["task_id"] == task_id
    assert meta["filename"] == "毕业论文_格式检测报告.pdf"
    assert meta["source_filename"] == "毕业论文.docx"
    assert meta["created_at"].endswith("Z")
    assert meta["expires_at"].endswith("Z")
    assert meta["expires_at"] > meta["created_at"]


def test_download_falls_back_when_sidecar_is_missing(tmp_path, monkeypatch) -> None:
    client, task_id, report_id = _create_report(tmp_path, monkeypatch)
    (tmp_path / "reports" / f"{report_id}.json").unlink()
    store.delete(task_id)

    downloaded = client.get(f"/api/v1/report/download/{report_id}")

    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")
    # 没有 sidecar 时用通用文件名，不能 500，也不能把任务号当文件名
    disposition = downloaded.headers["content-disposition"]
    assert "attachment" in disposition
    assert quote("格式检测报告.pdf") in disposition


def test_download_404_when_pdf_missing_even_if_sidecar_exists(tmp_path, monkeypatch) -> None:
    client, task_id, report_id = _create_report(tmp_path, monkeypatch)
    (tmp_path / "reports" / f"{report_id}.pdf").unlink()
    store.delete(task_id)

    assert client.get(f"/api/v1/report/download/{report_id}").status_code == 404

from io import BytesIO
from docx import Document
from fastapi.testclient import TestClient

from backend.app.api import upload
from backend.app.main import app
from backend.app.services import report as report_service
from backend.app.services.task_store import TaskRecord, store


def make_docx() -> bytes:
    document = Document()
    document.add_paragraph("正文")
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_create_and_download_report_then_removes_source(tmp_path, monkeypatch) -> None:
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
    source = upload_dir / f"{task_id}.docx"
    assert client.post("/api/v1/detect/start", json={"task_id": task_id}).status_code == 200
    assert not source.exists()

    created = client.post("/api/v1/report/create", json={"task_id": task_id})
    assert created.status_code == 200
    data = created.json()["data"]
    assert data["report_id"] == f"R{task_id}"
    assert data["filename"] == "毕业论文_格式检测报告.pdf"
    assert (report_dir / f"R{task_id}.pdf").read_bytes().startswith(b"%PDF")

    downloaded = client.get(f"/api/v1/report/download/R{task_id}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/pdf")
    assert downloaded.content.startswith(b"%PDF")
    store.delete(task_id)


def test_report_requires_completed_task(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path)
    client = TestClient(app)
    task_id = "Tpending"
    store.put(TaskRecord(task_id=task_id, filename="paper.docx"))

    response = client.post("/api/v1/report/create", json={"task_id": task_id})
    assert response.status_code == 409
    assert response.json()["detail"] == "检测尚未完成"
    store.delete(task_id)


def test_delete_task_removes_task_source_and_report(tmp_path, monkeypatch) -> None:
    upload_dir = tmp_path / "uploads"
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(upload, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(report_service, "REPORT_DIR", report_dir)
    client = TestClient(app)

    task_id = "Tdelete123"
    store.put(TaskRecord(task_id=task_id, filename="paper.docx", status="completed"))
    upload_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    (upload_dir / f"{task_id}.docx").write_bytes(b"source")
    (report_dir / f"R{task_id}.pdf").write_bytes(b"%PDF-test")

    response = client.delete(f"/api/v1/task/{task_id}")
    assert response.status_code == 200
    assert store.get(task_id) is None
    assert not (upload_dir / f"{task_id}.docx").exists()
    assert not (report_dir / f"R{task_id}.pdf").exists()


def test_download_report_rejects_unknown_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(report_service, "REPORT_DIR", tmp_path)
    response = TestClient(app).get("/api/v1/report/download/Rmissing")
    assert response.status_code == 404

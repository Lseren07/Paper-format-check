from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from backend.app.api import upload
from backend.app.main import app


def make_docx_bytes() -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" />',
        )
    return stream.getvalue()


def test_upload_valid_docx(tmp_path, monkeypatch) -> None:
    # 把"保存目录"换成 pytest 的临时目录，避免测试污染真实 uploads/（教学点：测试要隔离）
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path)

    content = make_docx_bytes()
    response = TestClient(app).post(
        "/api/v1/paper/upload",
        files={"file": ("thesis.docx", content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert body["data"]["status"] == "uploaded"
    assert body["data"]["filename"] == "thesis.docx"
    assert body["data"]["size"] == len(content)
    # 成功时应恰好保存了一个文件，且文件名以任务ID开头
    saved = list(tmp_path.iterdir())
    assert len(saved) == 1
    assert saved[0].name.startswith("T")


def test_upload_rejects_wrong_extension(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path)

    response = TestClient(app).post(
        "/api/v1/paper/upload",
        files={"file": ("virus.exe", b"MZ...", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_upload_rejects_invalid_docx_content(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path)

    response = TestClient(app).post(
        "/api/v1/paper/upload",
        files={"file": ("broken.docx", b"not a zip archive", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_upload_rejects_invalid_document_xml(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path)

    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "not valid XML")

    response = TestClient(app).post(
        "/api/v1/paper/upload",
        files={"file": ("fake.docx", stream.getvalue(), "application/octet-stream")},
    )

    assert response.status_code == 400
    assert list(tmp_path.iterdir()) == []


def test_upload_creates_nested_upload_directory(tmp_path, monkeypatch) -> None:
    upload_dir = tmp_path / "missing" / "nested"
    monkeypatch.setattr(upload, "UPLOAD_DIR", upload_dir)

    response = TestClient(app).post(
        "/api/v1/paper/upload",
        files={"file": ("thesis.docx", make_docx_bytes(), "application/octet-stream")},
    )

    assert response.status_code == 200
    assert upload_dir.is_dir()
    assert len(list(upload_dir.glob("*.docx"))) == 1


def test_upload_cleans_partial_file_when_write_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path)
    original_open = Path.open

    class FailingWriter:
        def __init__(self, path: Path) -> None:
            self.file = original_open(path, "wb")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.file.close()
            return False

        def write(self, chunk: bytes) -> None:
            self.file.write(chunk[:1])
            raise OSError("simulated disk write failure")

    def failing_open(path: Path, mode: str = "r", *args, **kwargs):
        if mode == "wb":
            return FailingWriter(path)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)

    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/v1/paper/upload",
        files={"file": ("thesis.docx", make_docx_bytes(), "application/octet-stream")},
    )

    assert response.status_code == 500
    assert list(tmp_path.iterdir()) == []


def test_upload_rejects_too_large(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path)
    # 把上限临时改成 0MB：任何非空文件都算超限（不真的去传50MB来测）
    monkeypatch.setattr(upload, "MAX_UPLOAD_MB", 0)

    response = TestClient(app).post(
        "/api/v1/paper/upload",
        files={"file": ("big.docx", b"x" * 1024, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 413
    # 超限后残留文件应被清理干净
    assert list(tmp_path.iterdir()) == []

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend.app.main import app
from backend.app.models.contracts import Document, ErrorItem


client = TestClient(app)


def test_health_endpoint_returns_api_version() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "paper-checker-backend",
    }


def test_document_contract_has_stable_top_level_collections() -> None:
    document = Document(
        document_id="DOC001",
        source_filename="thesis.docx",
    )

    assert document.schema_version == "1.0"
    assert document.source_filename == "thesis.docx"
    assert document.metadata == {}
    assert document.sections == []
    assert document.paragraphs == []
    assert document.tables == []
    assert document.headers == []
    assert document.footers == []
    assert document.pages == []


def test_error_contract_uses_current_and_expected_fields() -> None:
    error = ErrorItem(
        error_id="ERR001",
        type="font_error",
        location="第二章 第一节",
        content="这是错误文本",
        current="黑体 小四",
        expected="宋体 小四",
    )

    assert error.model_dump() == {
        "error_id": "ERR001",
        "type": "font_error",
        "location": "第二章 第一节",
        "content": "这是错误文本",
        "current": "黑体 小四",
        "expected": "宋体 小四",
    }


def test_error_contract_requires_current_and_expected_fields() -> None:
    with pytest.raises(ValidationError):
        ErrorItem(
            error_id="ERR001",
            type="font_error",
            location="摘要",
            content="文本",
        )

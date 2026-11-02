"""引擎鉴权契约：除健康检查外都必须带 X-Format-Key。"""

import pytest
from fastapi.testclient import TestClient

from backend.app.api import upload
from backend.app.main import app, validate_startup_config
from backend.app.security import require_engine_key
from backend.app.services import report as report_service

TEST_KEY = "test-key"


@pytest.fixture(autouse=True)
def _real_auth(_bypass_engine_key):
    """本模块要测真实鉴权，先摘掉 conftest 的绕过。"""
    app.dependency_overrides.pop(require_engine_key, None)
    yield


def test_request_without_key_is_rejected() -> None:
    response = TestClient(app).get("/api/v1/rule/list")

    assert response.status_code == 401
    assert response.json()["detail"] == "无效的服务密钥"


def test_request_with_wrong_key_is_rejected() -> None:
    response = TestClient(app).get("/api/v1/rule/list", headers={"X-Format-Key": "not-the-key"})

    assert response.status_code == 401


def test_request_with_correct_key_passes() -> None:
    response = TestClient(app).get("/api/v1/rule/list", headers={"X-Format-Key": TEST_KEY})

    assert response.status_code == 200
    assert response.json()["code"] == 200


def test_health_check_needs_no_key() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_engine_key_env_fails_closed(monkeypatch) -> None:
    """密钥没配置时不能退化成裸服务。"""
    monkeypatch.delenv("FORMAT_ENGINE_KEY", raising=False)

    response = TestClient(app).get("/api/v1/rule/list", headers={"X-Format-Key": ""})

    assert response.status_code == 401


def test_startup_rejects_missing_engine_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("FORMAT_ENGINE_KEY", raising=False)
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(report_service, "REPORT_DIR", tmp_path / "reports")

    with pytest.raises(RuntimeError, match="FORMAT_ENGINE_KEY"):
        validate_startup_config()


def test_startup_rejects_missing_rules_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FORMAT_ENGINE_KEY", TEST_KEY)
    monkeypatch.setenv("PAPER_RULES_DIR", str(tmp_path / "no-such-rules"))
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(report_service, "REPORT_DIR", tmp_path / "reports")

    with pytest.raises(RuntimeError, match="规则目录不存在"):
        validate_startup_config()


def test_startup_creates_working_dirs(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FORMAT_ENGINE_KEY", TEST_KEY)
    uploads = tmp_path / "uploads"
    reports = tmp_path / "reports"
    monkeypatch.setattr(upload, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(report_service, "REPORT_DIR", reports)

    validate_startup_config()

    assert uploads.is_dir()
    assert reports.is_dir()

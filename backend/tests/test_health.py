from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "paper-checker-backend",
        "version": "0.1.0",
        "contract_version": "1.0.0",
    }

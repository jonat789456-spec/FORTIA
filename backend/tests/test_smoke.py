from fastapi.testclient import TestClient

from app.main import app


def test_system_status() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/system/status")
    assert response.status_code == 200
    assert response.json()["service"] == "fortnite-ia-backend"


def test_session_lifecycle() -> None:
    client = TestClient(app)
    created = client.post("/api/v1/sessions")
    assert created.status_code == 200
    session_id = created.json()["sessionId"]
    started = client.post(f"/api/v1/sessions/{session_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "analyzing"


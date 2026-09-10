from fastapi.testclient import TestClient

from app.main import app

# Using TestClient as a context manager ensures FastAPI startup events
# (DB table creation) run before requests are sent.
client = TestClient(app)
client.__enter__()


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_process_rejects_unsupported_file():
    files = {"file": ("note.txt", b"hello world", "text/plain")}
    data = {"document_type": "invoice"}
    res = client.post("/api/documents/process", data=data, files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "REJECTED"


def test_list_documents_returns_array():
    res = client.get("/api/documents")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

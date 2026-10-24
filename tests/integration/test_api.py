from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_ok(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "SMY Agent"}


def test_health_exposes_no_infrastructure_details(client: TestClient) -> None:
    body = client.get("/api/v1/health").text.lower()
    for leak in ("python", "sqlite", "mysql", "version", "/home", "host"):
        assert leak not in body


def test_ready_reports_checks(client: TestClient) -> None:
    r = client.get("/api/v1/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["checks"]["config"] == "ok"


def test_request_id_generated_and_echoed(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert len(r.headers["x-request-id"]) >= 8
    r2 = client.get("/api/v1/health", headers={"X-Request-ID": "abc12345-test"})
    assert r2.headers["x-request-id"] == "abc12345-test"


def test_malicious_request_id_replaced(client: TestClient) -> None:
    r = client.get("/api/v1/health", headers={"X-Request-ID": "bad\r\nid<script>"})
    assert "script" not in r.headers["x-request-id"]


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "http_404"
    assert "request_id" in r.json()["error"]


def test_unhandled_error_is_generic(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("internal detail password=hunter2")

    r = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert "hunter2" not in r.text and "internal detail" not in r.text


def test_unhandled_error_keeps_request_id(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    r = TestClient(app, raise_server_exceptions=False).get(
        "/boom", headers={"X-Request-ID": "trace-12345678"}
    )
    assert r.status_code == 500
    assert r.headers["x-request-id"] == "trace-12345678"
    assert r.json()["error"]["request_id"] == "trace-12345678"


def test_docs_available_in_development(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200


def test_docs_disabled_in_production(prod_settings: Settings) -> None:
    c = TestClient(create_app(prod_settings))
    assert c.get("/docs").status_code == 404
    assert c.get("/openapi.json").status_code == 404


def test_ready_reports_database_failure(settings: Settings) -> None:
    from app.infrastructure.database import Database

    broken = Database("sqlite:////nonexistent-dir/x.db")
    r = TestClient(create_app(settings, database=broken)).get("/api/v1/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "not_ready", "checks": {"config": "ok", "database": "fail"}}

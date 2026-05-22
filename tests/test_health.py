from app.main import build_health_payload


def test_build_health_payload_reports_all_dependencies_ok():
    payload = build_health_payload(db_ok=True, redis_ok=True, qdrant_ok=True)

    assert payload == {
        "status": "ok",
        "dependencies": {"database": "ok", "redis": "ok", "qdrant": "ok"},
    }


def test_build_health_payload_reports_degraded():
    payload = build_health_payload(db_ok=True, redis_ok=False, qdrant_ok=True)

    assert payload["status"] == "degraded"
    assert payload["dependencies"]["redis"] == "error"

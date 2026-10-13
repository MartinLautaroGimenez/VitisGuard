import json
from datetime import date, datetime, timedelta, timezone

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from vitisguard_server import db
from vitisguard_server.app import create_app
from vitisguard_server.settings import Settings


@pytest.fixture
def env(tmp_path):
    app = create_app(Settings(data_dir=tmp_path, weekly_alert_threshold=5))
    token = db.add_trap(app.state.db, "trampa-001", "Finca de prueba", -33.0, -68.8)
    return TestClient(app), token


def jpeg_with_moths(n):
    img = np.full((900, 1200, 3), 225, np.uint8)
    for i in range(n):
        cv2.ellipse(img, (100 + (i % 8) * 130, 120 + (i // 8) * 150), (24, 9), 20, 0, 360,
                    (45, 55, 70), -1)
    return cv2.imencode(".jpg", img)[1].tobytes()


def post(client, token, n, taken_at, **meta):
    meta = {"taken_at": taken_at.isoformat(), **meta}
    return client.post(
        "/api/v1/captures",
        headers={"Authorization": f"Bearer {token}"},
        data={"metadata": json.dumps(meta)},
        files={"image": ("trap.jpg", jpeg_with_moths(n), "image/jpeg")},
    )


T0 = datetime(2026, 10, 12, 13, 0, tzinfo=timezone.utc)


def test_rejects_bad_token(env):
    client, _ = env
    assert post(client, "nope", 1, T0).status_code == 401


def test_new_captures_are_the_difference(env):
    client, token = env
    assert post(client, token, 3, T0).json()["count_new"] == 3
    r = post(client, token, 7, T0 + timedelta(days=1)).json()
    assert (r["count_total"], r["count_new"]) == (7, 4)
    assert r["detector"] == "classic"


def test_retry_is_idempotent(env):
    client, token = env
    first = post(client, token, 3, T0).json()
    again = post(client, token, 3, T0).json()
    assert again["duplicate"] and again["capture_id"] == first["capture_id"]
    assert len(client.get("/api/v1/traps/trampa-001/captures").json()) == 1


def test_liner_change_detected_by_drop(env):
    client, token = env
    post(client, token, 20, T0)
    r = post(client, token, 2, T0 + timedelta(days=1)).json()
    assert r["liner_changed"] and r["count_new"] == 2


def test_summary_degree_days_and_alert(env):
    client, token = env
    temps = [{"t": (T0 - timedelta(hours=h)).isoformat(), "c": 20.0, "h": 35.0} for h in range(24)]
    post(client, token, 2, T0, temperatures=temps)
    post(client, token, 6, T0 + timedelta(days=1))
    s = client.get("/api/v1/traps/trampa-001/summary", params={"today": "2026-10-13"}).json()
    assert s["degree_days"] == pytest.approx(20.0)  # dos días locales, 10 GD cada uno
    assert s["this_week"] == 6
    assert s["alert"] is True
    assert s["season_start"] == date(2026, 7, 1).isoformat()
    conn = client.app.state.db
    assert conn.execute("SELECT COUNT(*) FROM temperatures WHERE humidity = 35").fetchone()[0] == 24


def test_list_traps_shows_last_capture(env):
    client, token = env
    post(client, token, 4, T0)
    traps = client.get("/api/v1/traps").json()
    assert traps[0]["id"] == "trampa-001" and traps[0]["last_count_total"] == 4


def test_naive_timestamp_rejected(env):
    client, token = env
    assert post(client, token, 1, T0.replace(tzinfo=None)).status_code == 422

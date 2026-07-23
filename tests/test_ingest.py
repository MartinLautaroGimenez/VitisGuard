"""Tests end-to-end de la ingesta HTTP (con la IA deshabilitada en modo testing)."""
import base64
import json

from app.extensions import db
from app.models import Alert, Capture, Node, Reading
from app.alerts.engine import check_offline_nodes, evaluate_capture_threshold


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_ingest_requires_token(client, jpeg_bytes):
    resp = client.post("/api/ingest", data={"image": (bytes(jpeg_bytes), "t.jpg")})
    assert resp.status_code == 401


def test_ingest_multipart(client, node, jpeg_bytes):
    import io
    data = {
        "data": json.dumps({"temperature": 22.5, "humidity": 48.0}),
        "image": (io.BytesIO(jpeg_bytes), "trap.jpg"),
    }
    resp = client.post("/api/ingest", data=data, content_type="multipart/form-data",
                       headers={"Authorization": f"Bearer {node.api_token}"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "ok"
    # se creó la lectura y la captura (IA off -> pending)
    assert Reading.query.count() == 1
    assert Capture.query.count() == 1
    cap = Capture.query.first()
    assert cap.status == "pending"


def test_ingest_json_base64(client, node, jpeg_bytes):
    payload = {
        "token": node.api_token,
        "temperature": 20.0, "humidity": 55.0,
        "image_b64": base64.b64encode(jpeg_bytes).decode(),
    }
    resp = client.post("/api/ingest", json=payload)
    assert resp.status_code == 201
    assert Capture.query.count() == 1


def test_env_only_reading(client, node):
    resp = client.post("/api/ingest", json={"token": node.api_token,
                                            "temperature": 19.1, "humidity": 60.2})
    assert resp.status_code == 201
    assert Reading.query.count() == 1
    assert Capture.query.count() == 0


def test_capture_threshold_alert(app, node):
    # Insertamos capturas con conteo suficiente para superar el umbral.
    for _ in range(3):
        db.session.add(Capture(node_id=node.id, image_path="x.jpg",
                               detection_count=2, species="Lobesia botrana",
                               status="processed"))
    db.session.commit()
    alert = evaluate_capture_threshold(node)
    assert alert is not None
    assert alert.type == "threshold"
    assert Alert.query.filter_by(type="threshold").count() == 1
    # No debe duplicar mientras siga abierta.
    assert evaluate_capture_threshold(node) is None


def test_offline_alert(app):
    from datetime import timedelta
    from app.models import utcnow
    n = Node(node_id="VG-OFF", api_token="tk", last_seen=utcnow() - timedelta(hours=48))
    db.session.add(n)
    db.session.commit()
    created = check_offline_nodes()
    assert created >= 1
    assert Alert.query.filter_by(type="offline").count() >= 1


def test_api_nodes(client, node):
    resp = client.get("/api/nodes")
    assert resp.status_code == 200
    assert any(x["node_id"] == "VG-TEST" for x in resp.get_json())

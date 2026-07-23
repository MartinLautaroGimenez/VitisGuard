"""API JSON consumida por el dashboard (Leaflet + Chart.js) vía fetch()."""
from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import Alert, Capture, Node, Reading, utcnow

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _days_arg(default: int = 7) -> int:
    try:
        return max(1, min(365, int(request.args.get("days", default))))
    except (ValueError, TypeError):
        return default


@api_bp.get("/nodes")
def nodes():
    return jsonify([n.to_dict() for n in Node.query.order_by(Node.node_id).all()])


@api_bp.get("/nodes/<node_id>")
def node_detail(node_id):
    node = Node.query.filter_by(node_id=node_id).first_or_404()
    return jsonify(node.to_dict())


@api_bp.get("/nodes/<node_id>/readings")
def node_readings(node_id):
    node = Node.query.filter_by(node_id=node_id).first_or_404()
    since = utcnow() - timedelta(days=_days_arg())
    rows = (node.readings.filter(Reading.timestamp >= since)
            .order_by(Reading.timestamp).all())
    return jsonify([r.to_dict() for r in rows])


@api_bp.get("/nodes/<node_id>/captures-per-day")
def node_captures_per_day(node_id):
    node = Node.query.filter_by(node_id=node_id).first_or_404()
    return jsonify(_captures_per_day(node_id=node.id, days=_days_arg(30)))


@api_bp.get("/series/captures-per-day")
def series_captures_per_day():
    """Serie de capturas/día agregada (todos los nodos o uno filtrado por ?node=)."""
    node_id = None
    node_key = request.args.get("node")
    if node_key:
        node = Node.query.filter_by(node_id=node_key).first_or_404()
        node_id = node.id
    return jsonify(_captures_per_day(node_id=node_id, days=_days_arg(30)))


def _captures_per_day(node_id=None, days=30):
    since = utcnow() - timedelta(days=days)
    day = func.date(Capture.timestamp)
    q = (db.session.query(day.label("day"),
                          func.coalesce(func.sum(Capture.detection_count), 0))
         .filter(Capture.timestamp >= since))
    if node_id is not None:
        q = q.filter(Capture.node_id == node_id)
    rows = q.group_by(day).order_by(day).all()
    return [{"day": str(d), "count": int(c or 0)} for d, c in rows]


@api_bp.get("/captures")
def captures():
    q = Capture.query
    node_key = request.args.get("node")
    if node_key:
        node = Node.query.filter_by(node_id=node_key).first()
        q = q.filter(Capture.node_id == (node.id if node else -1))
    species = request.args.get("species")
    if species:
        q = q.filter(Capture.species == species)
    limit = min(200, int(request.args.get("limit", 60)))
    rows = q.order_by(Capture.timestamp.desc()).limit(limit).all()
    return jsonify([c.to_dict() for c in rows])


@api_bp.get("/captures/<int:capture_id>")
def capture_detail(capture_id):
    c = Capture.query.get_or_404(capture_id)
    data = c.to_dict()
    data["detections"] = [d.to_dict() for d in c.detections]
    return jsonify(data)


@api_bp.get("/alerts")
def alerts():
    q = Alert.query
    if request.args.get("open") == "true":
        q = q.filter_by(acknowledged=False)
    rows = q.order_by(Alert.timestamp.desc()).limit(200).all()
    return jsonify([a.to_dict() for a in rows])


@api_bp.post("/alerts/<int:alert_id>/ack")
def ack_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.acknowledged = True
    db.session.commit()
    return jsonify(status="ok", id=alert.id)


@api_bp.get("/stats/overview")
def stats_overview():
    now = utcnow()
    week_ago = now - timedelta(days=7)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    nodes_all = Node.query.filter_by(active=True).all()
    online = sum(1 for n in nodes_all if n.is_online)

    captures_week = (db.session.query(func.coalesce(func.sum(Capture.detection_count), 0))
                     .filter(Capture.timestamp >= week_ago).scalar()) or 0
    captures_today = (db.session.query(func.coalesce(func.sum(Capture.detection_count), 0))
                      .filter(Capture.timestamp >= today).scalar()) or 0
    open_alerts = Alert.query.filter_by(acknowledged=False).count()

    last24 = now - timedelta(hours=24)
    avg = (db.session.query(func.avg(Reading.temperature), func.avg(Reading.humidity))
           .filter(Reading.timestamp >= last24).first())
    avg_temp = round(avg[0], 1) if avg and avg[0] is not None else None
    avg_hum = round(avg[1], 1) if avg and avg[1] is not None else None

    return jsonify(
        nodes_total=len(nodes_all),
        nodes_online=online,
        captures_week=int(captures_week),
        captures_today=int(captures_today),
        open_alerts=open_alerts,
        avg_temp=avg_temp,
        avg_humidity=avg_hum,
    )

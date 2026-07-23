"""Motor de alertas por umbral.

  * ``evaluate_capture_threshold``: capturas de plaga en la ventana móvil (p. ej. 7 días)
    ≥ umbral (p. ej. 5) para una trampa -> dispara alerta (con deduplicación).
  * ``check_offline_nodes``: nodo activo que no reporta hace > N horas -> alerta offline.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from flask import current_app
from sqlalchemy import func

from ..extensions import db
from ..models import Alert, Capture, Node, utcnow
from .notifier import notify

log = logging.getLogger("vitisguard.alerts")


def _has_open_alert(node: Node, alert_type: str) -> bool:
    return (Alert.query
            .filter_by(node_id=node.id, type=alert_type, acknowledged=False)
            .count() > 0)


def _raise_alert(node: Node, *, type: str, level: str, message: str, value=None) -> Alert:
    alert = Alert(node_id=node.id, type=type, level=level, message=message, value=value)
    db.session.add(alert)
    db.session.commit()
    log.info("Alerta creada (%s) nodo=%s", type, node.node_id)
    notify(alert)
    return alert


def evaluate_capture_threshold(node: Node) -> Alert | None:
    """Suma las plagas detectadas en la ventana móvil; si supera el umbral, alerta."""
    threshold = current_app.config.get("ALERT_CAPTURE_THRESHOLD", 5)
    window_days = current_app.config.get("ALERT_WINDOW_DAYS", 7)
    since = utcnow() - timedelta(days=window_days)

    total = (db.session.query(func.coalesce(func.sum(Capture.detection_count), 0))
             .filter(Capture.node_id == node.id, Capture.timestamp >= since)
             .scalar()) or 0

    if total < threshold:
        return None
    if _has_open_alert(node, "threshold"):
        return None

    return _raise_alert(
        node, type="threshold", level="critical",
        message=(f"{int(total)} capturas de Lobesia botrana en {window_days} días "
                 f"(umbral {threshold}). Se recomienda intervención."),
        value=float(total),
    )


def check_offline_nodes() -> int:
    """Recorre nodos activos y alerta los que dejaron de reportar. Devuelve cuántos."""
    hours = current_app.config.get("NODE_OFFLINE_HOURS", 6)
    cutoff = utcnow() - timedelta(hours=hours)
    count = 0
    for node in Node.query.filter_by(active=True).all():
        last = node.last_seen
        if last is not None and last.tzinfo is None:
            from datetime import timezone
            last = last.replace(tzinfo=timezone.utc)
        offline = last is None or last < cutoff
        if offline and not _has_open_alert(node, "offline"):
            _raise_alert(
                node, type="offline", level="warning",
                message=f"El nodo no reporta hace más de {hours} h.",
            )
            count += 1
    return count

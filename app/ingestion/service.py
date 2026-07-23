"""Pipeline único de ingesta: llega tanto desde HTTP como desde MQTT.

Responsabilidades:
  * resolver / auto-registrar el nodo,
  * guardar la imagen JPEG,
  * persistir la lectura ambiental (Reading),
  * llamar al microservicio de IA y persistir la captura (Capture + Detection),
  * actualizar last_seen y evaluar alertas por umbral.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

from ..ai import client as ai_client
from ..alerts.engine import evaluate_capture_threshold
from ..extensions import db
from ..models import Capture, Detection, Node, Reading, generate_token, utcnow

log = logging.getLogger("vitisguard.ingest")


def get_or_create_node(node_id: str, source: str = "auto") -> Node:
    node = Node.query.filter_by(node_id=node_id).first()
    if node is None:
        node = Node(
            node_id=node_id,
            name=f"Nodo {node_id}",
            api_token=generate_token(),
            finca="(auto-registrado)",
        )
        db.session.add(node)
        db.session.commit()
        log.info("Nodo auto-registrado: %s (via %s)", node_id, source)
    return node


def record_reading(node: Node, *, temperature=None, humidity=None, battery_v=None,
                   timestamp: datetime | None = None, source: str = "http") -> Reading:
    reading = Reading(
        node_id=node.id,
        timestamp=timestamp or utcnow(),
        temperature=temperature,
        humidity=humidity,
        battery_v=battery_v,
        source=source,
    )
    if battery_v is not None:
        node.battery_v = battery_v
    node.last_seen = utcnow()
    db.session.add(reading)
    db.session.commit()
    return reading


def record_capture(node: Node, image_bytes: bytes, *,
                   timestamp: datetime | None = None, source: str = "http") -> Capture:
    ts = timestamp or utcnow()
    rel_path = _save_image(node.node_id, ts, image_bytes)

    capture = Capture(
        node_id=node.id,
        timestamp=ts,
        image_path=rel_path,
        status="pending",
    )
    node.last_seen = utcnow()
    db.session.add(capture)
    db.session.commit()

    # --- Clasificación por IA (con fallback elegante) ---
    result = ai_client.detect(image_bytes)
    if result is not None:
        capture.detection_count = result.count
        capture.species = result.species
        capture.confidence = result.confidence
        capture.status = "processed"
        for d in result.detections:
            db.session.add(Detection(
                capture_id=capture.id,
                x=d.x, y=d.y, w=d.w, h=d.h,
                class_name=d.class_name, confidence=d.confidence,
            ))
        if result.annotated_png:
            capture.annotated_path = _save_annotated(node.node_id, ts, result.annotated_png)
        db.session.commit()

    # --- Evaluación de alertas por umbral ---
    evaluate_capture_threshold(node)
    return capture


def process_capture(node: Node, image_bytes: bytes, *, temperature=None, humidity=None,
                    battery_v=None, timestamp: datetime | None = None,
                    source: str = "http") -> Capture:
    """Payload completo (imagen + ambiente), típico del camino HTTP."""
    ts = timestamp or utcnow()
    record_reading(node, temperature=temperature, humidity=humidity,
                   battery_v=battery_v, timestamp=ts, source=source)
    return record_capture(node, image_bytes, timestamp=ts, source=source)


# --------------------------------------------------------------------------- #
# Helpers de almacenamiento de imágenes
# --------------------------------------------------------------------------- #
def _images_dir() -> Path:
    return Path(current_app.config["IMAGES_DIR"])


def _stamp(ts: datetime) -> str:
    ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def _save_image(node_id: str, ts: datetime, image_bytes: bytes) -> str:
    node_dir = _images_dir() / node_id
    node_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_stamp(ts)}.jpg"
    (node_dir / filename).write_bytes(image_bytes)
    return f"{node_id}/{filename}"


def _save_annotated(node_id: str, ts: datetime, png_bytes: bytes) -> str:
    node_dir = _images_dir() / node_id
    node_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_stamp(ts)}_annot.png"
    (node_dir / filename).write_bytes(png_bytes)
    return f"{node_id}/{filename}"

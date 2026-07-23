"""Ingesta por HTTP.

El nodo de campo (SIM800L) hace ``POST /api/ingest`` con la imagen JPEG de la trampa
y las variables ambientales, autenticándose con un token Bearer propio del nodo.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..models import Node
from . import service

log = logging.getLogger("vitisguard.ingest")

ingest_bp = Blueprint("ingest", __name__)


def _json_body() -> dict:
    if request.is_json:
        try:
            return request.get_json(silent=True) or {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _authenticate() -> Node | None:
    """Resuelve el nodo por token Bearer, o campo 'token' de form/query/JSON."""
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):].strip()
    token = (token or request.form.get("token") or request.args.get("token")
             or _json_body().get("token"))
    if not token:
        return None
    return Node.query.filter_by(api_token=token).first()


def _parse_payload() -> dict:
    """Campos desde JSON, desde el campo 'data' (multipart) o sueltos del form."""
    data = dict(_json_body())
    if "data" in request.form:
        try:
            data.update(json.loads(request.form["data"]))
        except (ValueError, TypeError):
            pass
    for key in ("node_id", "temperature", "humidity", "battery_v", "timestamp"):
        if key in request.form and key not in data:
            data[key] = request.form[key]
    return data


def _extract_image(payload: dict) -> bytes | None:
    """Imagen desde multipart ('image') o base64 en JSON ('image_b64')."""
    image_file = request.files.get("image")
    if image_file:
        return image_file.read()
    b64 = payload.get("image_b64")
    if b64:
        if isinstance(b64, str) and b64.startswith("data:"):
            b64 = b64.split(",", 1)[-1]
        try:
            return base64.b64decode(b64)
        except (binascii.Error, ValueError, TypeError):
            return None
    return None


def _to_float(value):
    try:
        return float(value) if value is not None and value != "" else None
    except (ValueError, TypeError):
        return None


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


@ingest_bp.post("/api/ingest")
def ingest():
    node = _authenticate()
    if node is None:
        return jsonify(error="token inválido o ausente"), 401
    if not node.active:
        return jsonify(error="nodo inactivo"), 403

    payload = _parse_payload()
    temperature = _to_float(payload.get("temperature"))
    humidity = _to_float(payload.get("humidity"))
    battery_v = _to_float(payload.get("battery_v"))
    ts = _parse_ts(payload.get("timestamp"))

    image_bytes = _extract_image(payload)

    if image_bytes:
        capture = service.process_capture(
            node, image_bytes,
            temperature=temperature, humidity=humidity, battery_v=battery_v,
            timestamp=ts, source="http",
        )
        return jsonify(
            status="ok", capture_id=capture.id,
            detection_count=capture.detection_count, ai_status=capture.status,
        ), 201

    # Telemetría sin imagen -> solo lectura ambiental.
    service.record_reading(
        node, temperature=temperature, humidity=humidity, battery_v=battery_v,
        timestamp=ts, source="http",
    )
    return jsonify(status="ok", reading="stored"), 201


@ingest_bp.get("/api/health")
def health():
    return jsonify(status="ok", service="vitisguard")

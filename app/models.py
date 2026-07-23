"""Modelos de datos de VitisGuard (SQLAlchemy sobre SQLite)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from .extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_token() -> str:
    return secrets.token_hex(16)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite devuelve datetimes naive; los normalizamos a UTC-aware."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Node(db.Model):
    __tablename__ = "nodes"

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, default="")
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    finca = db.Column(db.String(120), nullable=False, default="")
    crop = db.Column(db.String(80), nullable=False, default="Vid")
    install_date = db.Column(db.DateTime(timezone=True), default=utcnow)
    last_seen = db.Column(db.DateTime(timezone=True), nullable=True)
    battery_v = db.Column(db.Float, nullable=True)
    api_token = db.Column(db.String(64), nullable=False, default=generate_token)
    active = db.Column(db.Boolean, nullable=False, default=True)

    readings = db.relationship("Reading", backref="node", lazy="dynamic",
                               cascade="all, delete-orphan")
    captures = db.relationship("Capture", backref="node", lazy="dynamic",
                               cascade="all, delete-orphan")
    alerts = db.relationship("Alert", backref="node", lazy="dynamic",
                             cascade="all, delete-orphan")

    @property
    def is_online(self) -> bool:
        last = _aware(self.last_seen)
        if last is None:
            return False
        hours = current_app.config.get("NODE_OFFLINE_HOURS", 6)
        return last >= utcnow() - timedelta(hours=hours)

    @property
    def open_alerts_count(self) -> int:
        return self.alerts.filter_by(acknowledged=False).count()

    @property
    def status(self) -> str:
        if not self.active:
            return "inactive"
        if self.open_alerts_count > 0:
            return "alert"
        return "online" if self.is_online else "offline"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "finca": self.finca,
            "crop": self.crop,
            "last_seen": _aware(self.last_seen).isoformat() if self.last_seen else None,
            "battery_v": self.battery_v,
            "active": self.active,
            "status": self.status,
            "open_alerts": self.open_alerts_count,
        }


class Reading(db.Model):
    __tablename__ = "readings"

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey("nodes.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)
    temperature = db.Column(db.Float, nullable=True)
    humidity = db.Column(db.Float, nullable=True)
    battery_v = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(8), nullable=False, default="http")  # http | mqtt

    def to_dict(self) -> dict:
        return {
            "timestamp": _aware(self.timestamp).isoformat(),
            "temperature": self.temperature,
            "humidity": self.humidity,
            "battery_v": self.battery_v,
            "source": self.source,
        }


class Capture(db.Model):
    __tablename__ = "captures"

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey("nodes.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)
    image_path = db.Column(db.String(255), nullable=False)       # relativo a IMAGES_DIR
    annotated_path = db.Column(db.String(255), nullable=True)
    detection_count = db.Column(db.Integer, nullable=False, default=0)
    species = db.Column(db.String(80), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(12), nullable=False, default="pending")  # pending | processed

    detections = db.relationship("Detection", backref="capture", lazy="select",
                                 cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_id": self.node.node_id if self.node else None,
            "timestamp": _aware(self.timestamp).isoformat(),
            "image_url": f"/media/{self.image_path}",
            "annotated_url": f"/media/{self.annotated_path}" if self.annotated_path else None,
            "detection_count": self.detection_count,
            "species": self.species,
            "confidence": self.confidence,
            "status": self.status,
        }


class Detection(db.Model):
    __tablename__ = "detections"

    id = db.Column(db.Integer, primary_key=True)
    capture_id = db.Column(db.Integer, db.ForeignKey("captures.id"), nullable=False, index=True)
    # bbox normalizado [0..1] respecto al tamaño de la imagen
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    w = db.Column(db.Float, nullable=False)
    h = db.Column(db.Float, nullable=False)
    class_name = db.Column(db.String(80), nullable=True)
    confidence = db.Column(db.Float, nullable=True)

    def to_dict(self) -> dict:
        return {
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "class_name": self.class_name, "confidence": self.confidence,
        }


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    node_id = db.Column(db.Integer, db.ForeignKey("nodes.id"), nullable=False, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=utcnow, index=True)
    type = db.Column(db.String(16), nullable=False, default="threshold")  # threshold | offline
    level = db.Column(db.String(12), nullable=False, default="warning")   # info|warning|critical
    message = db.Column(db.String(255), nullable=False, default="")
    value = db.Column(db.Float, nullable=True)
    acknowledged = db.Column(db.Boolean, nullable=False, default=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_id": self.node.node_id if self.node else None,
            "node_name": self.node.name if self.node else None,
            "timestamp": _aware(self.timestamp).isoformat(),
            "type": self.type,
            "level": self.level,
            "message": self.message,
            "value": self.value,
            "acknowledged": self.acknowledged,
        }

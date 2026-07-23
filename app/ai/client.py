"""Cliente HTTP hacia el microservicio de IA (ai_service/).

El core Flask NO depende de torch/ultralytics: delega la detección al microservicio
y degrada con elegancia si no está disponible (la captura queda en estado 'pending').
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field

import requests
from flask import current_app

log = logging.getLogger("vitisguard.ai")


@dataclass
class Detection:
    x: float
    y: float
    w: float
    h: float
    class_name: str | None = None
    confidence: float | None = None


@dataclass
class DetectionResult:
    count: int
    species: str | None = None
    confidence: float | None = None
    detections: list[Detection] = field(default_factory=list)
    annotated_png: bytes | None = None  # imagen anotada (PNG) opcional


def detect(image_bytes: bytes) -> DetectionResult | None:
    """Envía la imagen al microservicio de IA y devuelve el resultado.

    Devuelve ``None`` si la IA está deshabilitada o el servicio no responde,
    lo que hace que la captura se persista con estado 'pending'.
    """
    if not current_app.config.get("AI_ENABLED"):
        return None

    url = current_app.config["AI_SERVICE_URL"].rstrip("/") + "/detect"
    timeout = current_app.config.get("AI_TIMEOUT", 8)

    try:
        resp = requests.post(
            url,
            files={"image": ("capture.jpg", image_bytes, "image/jpeg")},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("Microservicio IA no disponible (%s): captura queda 'pending'", exc)
        return None

    annotated = None
    if data.get("annotated_png_b64"):
        try:
            annotated = base64.b64decode(data["annotated_png_b64"])
        except (ValueError, TypeError):
            annotated = None

    detections = [
        Detection(
            x=d.get("x", 0.0), y=d.get("y", 0.0),
            w=d.get("w", 0.0), h=d.get("h", 0.0),
            class_name=d.get("class_name"),
            confidence=d.get("confidence"),
        )
        for d in data.get("detections", [])
    ]

    return DetectionResult(
        count=int(data.get("count", len(detections))),
        species=data.get("species"),
        confidence=data.get("confidence"),
        detections=detections,
        annotated_png=annotated,
    )

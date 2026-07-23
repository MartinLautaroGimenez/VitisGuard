"""Ingesta por MQTT (Mosquitto sobre TLS).

Corre en un hilo de fondo y suscribe dos tópicos por nodo:
  * ``<base>/<node_id>/env``   -> JSON de telemetría (temp/humedad/batería)
  * ``<base>/<node_id>/image`` -> JPEG en base64 (imágenes chicas)

Ambos convergen en el mismo pipeline que la ingesta HTTP (service.py).
Patrón IoT habitual: MQTT liviano para telemetría, HTTP para imágenes grandes.
"""
from __future__ import annotations

import base64
import json
import logging

from flask import Flask

log = logging.getLogger("vitisguard.mqtt")

_client = None  # referencia global para no arrancar dos veces


def start_mqtt_subscriber(app: Flask) -> None:
    global _client
    if _client is not None:
        return
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        log.error("paho-mqtt no instalado; la vía MQTT queda deshabilitada.")
        return

    cfg = app.config
    base = cfg["MQTT_TOPIC_BASE"]

    def on_connect(client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            log.error("Conexión MQTT rechazada (rc=%s)", reason_code)
            return
        client.subscribe([(f"{base}/+/env", 0), (f"{base}/+/image", 0)])
        log.info("Suscripto a MQTT %s://%s:%s (tópicos %s/+/{env,image})",
                 "tls" if cfg["MQTT_USE_TLS"] else "tcp",
                 cfg["MQTT_HOST"], cfg["MQTT_PORT"], base)

    def on_message(client, userdata, msg):
        with app.app_context():
            try:
                _handle_message(base, msg.topic, msg.payload)
            except Exception as exc:  # noqa: BLE001 - no romper el loop MQTT
                log.error("Error procesando mensaje MQTT %s: %s", msg.topic, exc)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    if cfg.get("MQTT_USERNAME"):
        client.username_pw_set(cfg["MQTT_USERNAME"], cfg.get("MQTT_PASSWORD"))
    if cfg["MQTT_USE_TLS"]:
        client.tls_set(ca_certs=cfg["MQTT_CA_CERT"])

    try:
        client.connect(cfg["MQTT_HOST"], cfg["MQTT_PORT"], keepalive=60)
    except OSError as exc:
        log.error("No se pudo conectar al broker MQTT (%s). ¿Está mosquitto corriendo?", exc)
        return

    client.loop_start()  # hilo de fondo
    _client = client


def _handle_message(base: str, topic: str, payload: bytes) -> None:
    # topic = <base>/<node_id>/<kind>
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != base:
        return
    _, node_id, kind = parts

    # import perezoso para evitar ciclos en el arranque
    from . import service
    node = service.get_or_create_node(node_id, source="mqtt")

    if kind == "env":
        data = json.loads(payload.decode("utf-8"))
        service.record_reading(
            node,
            temperature=data.get("temperature"),
            humidity=data.get("humidity"),
            battery_v=data.get("battery_v"),
            source="mqtt",
        )
    elif kind == "image":
        image_bytes = _decode_image(payload)
        if image_bytes:
            service.record_capture(node, image_bytes, source="mqtt")


def _decode_image(payload: bytes) -> bytes | None:
    """Acepta JPEG crudo o base64 (con o sin envoltura JSON {'image': ...})."""
    # ¿JPEG crudo? (magic bytes FF D8 FF)
    if payload[:3] == b"\xff\xd8\xff":
        return payload
    text = payload.decode("utf-8", errors="ignore").strip()
    if text.startswith("{"):
        try:
            text = json.loads(text).get("image", "")
        except (ValueError, TypeError):
            return None
    if text.startswith("data:"):  # data URI
        text = text.split(",", 1)[-1]
    try:
        return base64.b64decode(text)
    except (ValueError, TypeError):
        return None

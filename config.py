"""Configuración de VitisGuard.

Las clases de config leen variables de entorno (ver .env.example). Se selecciona
la config con la variable de entorno ``VITISGUARD_CONFIG`` (development|production|testing)
o pasando el nombre a ``create_app``.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
IMAGES_DIR = STORAGE_DIR / "images"
CERTS_DIR = BASE_DIR / "certs"


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


class Config:
    """Configuración base común a todos los entornos."""

    # --- Flask ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "vitisguard-dev-secret-change-me")

    # --- Base de datos (SQLite por defecto; Postgres/Supabase vía DATABASE_URL) ---
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'vitisguard.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Con Postgres (Supabase) las tablas viven en un schema propio para no
    # ensuciar `public` ni quedar expuestas por PostgREST. En SQLite se ignora.
    _IS_POSTGRES = SQLALCHEMY_DATABASE_URI.startswith("postgres")
    DB_SCHEMA = os.environ.get("DB_SCHEMA", "vitisguard") if _IS_POSTGRES else None
    # pool_pre_ping evita conexiones muertas al pasar por el pooler de Supabase.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {"pool_pre_ping": True, "pool_recycle": 1800} if _IS_POSTGRES else {}
    )

    # --- Almacenamiento de imágenes ---
    IMAGES_DIR = str(IMAGES_DIR)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "16")) * 1024 * 1024

    # --- Microservicio de IA ---
    AI_ENABLED = _bool(os.environ.get("AI_ENABLED"), default=True)
    AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://127.0.0.1:8001")
    AI_TIMEOUT = float(os.environ.get("AI_TIMEOUT", "8"))

    # --- Motor de alertas ---
    # Umbral de capturas por trampa en una ventana de N días -> dispara alerta.
    ALERT_CAPTURE_THRESHOLD = int(os.environ.get("ALERT_CAPTURE_THRESHOLD", "5"))
    ALERT_WINDOW_DAYS = int(os.environ.get("ALERT_WINDOW_DAYS", "7"))
    # Un nodo se considera offline si no reporta en esta cantidad de horas.
    NODE_OFFLINE_HOURS = int(os.environ.get("NODE_OFFLINE_HOURS", "6"))
    SCHEDULER_ENABLED = _bool(os.environ.get("SCHEDULER_ENABLED"), default=True)

    # --- Notificaciones ---
    # backend: "log" (default, muestra en dashboard) | "email" | "whatsapp"
    NOTIFIER_BACKEND = os.environ.get("NOTIFIER_BACKEND", "log")
    # Email (SMTP) — stub listo para activar
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")
    # WhatsApp (Twilio) — stub listo para activar
    TWILIO_SID = os.environ.get("TWILIO_SID", "")
    TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN", "")
    TWILIO_FROM = os.environ.get("TWILIO_FROM", "")
    ALERT_WHATSAPP_TO = os.environ.get("ALERT_WHATSAPP_TO", "")

    # --- MQTT (Mosquitto sobre TLS) ---
    MQTT_ENABLED = _bool(os.environ.get("MQTT_ENABLED"), default=False)
    MQTT_HOST = os.environ.get("MQTT_HOST", "127.0.0.1")
    MQTT_PORT = int(os.environ.get("MQTT_PORT", "8883"))
    MQTT_USE_TLS = _bool(os.environ.get("MQTT_USE_TLS"), default=True)
    MQTT_CA_CERT = os.environ.get("MQTT_CA_CERT", str(CERTS_DIR / "ca.crt"))
    MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "")
    MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "")
    MQTT_TOPIC_BASE = os.environ.get("MQTT_TOPIC_BASE", "vitisguard")
    # Si un nodo publica por MQTT sin token, se acepta igualmente (canal ya cifrado/autenticado).
    MQTT_TRUST_CLIENTS = _bool(os.environ.get("MQTT_TRUST_CLIENTS"), default=True)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    DB_SCHEMA = None
    SQLALCHEMY_ENGINE_OPTIONS = {}
    AI_ENABLED = False
    MQTT_ENABLED = False
    SCHEDULER_ENABLED = False
    WTF_CSRF_ENABLED = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None) -> type[Config]:
    name = name or os.environ.get("VITISGUARD_CONFIG", "development")
    return CONFIG_MAP.get(name, DevelopmentConfig)

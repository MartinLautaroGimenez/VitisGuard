"""VitisGuard — application factory.

Consolida en una sola app Flask toda la capa de servidor:
ingesta (HTTP + MQTT), almacenamiento (SQLite), dashboard, API JSON y alertas.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, send_from_directory

from config import DATA_DIR, IMAGES_DIR, get_config
from .extensions import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("vitisguard")


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(get_config(config_name))

    _ensure_dirs()

    db.init_app(app)
    _configure_pg_schema(app)

    # Modelos + creación de tablas
    with app.app_context():
        from . import models  # noqa: F401  (registra los modelos)
        db.create_all()

    _register_blueprints(app)
    _register_media_route(app)
    _register_cli(app)

    # Los hilos/jobs de fondo solo deben correr en el proceso que efectivamente
    # sirve. Con el reloader de debug hay dos procesos: el hijo tiene
    # WERKZEUG_RUN_MAIN=true. En producción (sin debug) hay un solo proceso.
    if _should_start_background(app):
        if app.config.get("SCHEDULER_ENABLED"):
            _start_scheduler(app)
        if app.config.get("MQTT_ENABLED"):
            _start_mqtt(app)

    log.info("VitisGuard iniciada (config=%s)", type(app.config).__name__)
    return app


def _ensure_dirs() -> None:
    for path in (DATA_DIR, Path(IMAGES_DIR)):
        path.mkdir(parents=True, exist_ok=True)


def _configure_pg_schema(app: Flask) -> None:
    """Con Postgres (Supabase) aísla las tablas en un schema propio.

    El pooler de Supabase (Supavisor) no reenvía las ``options`` de conexión,
    así que fijamos el ``search_path`` en cada conexión con un listener y
    garantizamos que el schema exista antes de crear las tablas.
    """
    schema = app.config.get("DB_SCHEMA")
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not schema or not uri.startswith("postgres"):
        return

    from sqlalchemy import event, text

    with app.app_context():
        engine = db.engine

        @event.listens_for(engine, "connect")
        def _set_search_path(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            try:
                cur.execute(f'SET search_path TO "{schema}", public')
            finally:
                cur.close()

        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    log.info("Postgres: usando schema '%s' (search_path aislado).", schema)


def _should_start_background(app: Flask) -> bool:
    if app.testing:
        return False
    if app.debug:
        return os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    return True


def _register_blueprints(app: Flask) -> None:
    from .ingestion.http_routes import ingest_bp
    from .dashboard.routes import dashboard_bp
    from .api.routes import api_bp

    app.register_blueprint(ingest_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp)


def _register_media_route(app: Flask) -> None:
    """Sirve las imágenes almacenadas (fuera de /static)."""

    @app.route("/media/<path:filename>")
    def media(filename: str):
        return send_from_directory(app.config["IMAGES_DIR"], filename)


def _register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas de la base de datos."""
        db.create_all()
        print("Base de datos inicializada.")


def _start_scheduler(app: Flask) -> None:
    """APScheduler: chequeo periódico de nodos offline."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from .alerts.engine import check_offline_nodes

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(
        lambda: _run_in_context(app, check_offline_nodes),
        "interval",
        minutes=5,
        id="offline_check",
    )
    sched.start()
    log.info("Scheduler de alertas iniciado.")


def _start_mqtt(app: Flask) -> None:
    from .ingestion.mqtt_client import start_mqtt_subscriber

    start_mqtt_subscriber(app)


def _run_in_context(app: Flask, fn) -> None:
    with app.app_context():
        fn()

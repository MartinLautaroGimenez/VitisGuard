"""Extensiones Flask compartidas (evita import circular con la app factory)."""
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# El scheduler (APScheduler) se instancia perezosamente en la app factory
# para poder deshabilitarlo en tests / procesos worker.
scheduler = None

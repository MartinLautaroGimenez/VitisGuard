from __future__ import annotations

import hashlib
import secrets
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS traps (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,
    lat         REAL,
    lon         REAL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE TABLE IF NOT EXISTS captures (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    trap_id        TEXT NOT NULL REFERENCES traps(id),
    taken_at       TEXT NOT NULL,
    received_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    image          TEXT NOT NULL,
    annotated      TEXT NOT NULL,
    count_total    INTEGER NOT NULL,
    count_new      INTEGER NOT NULL,
    liner_changed  INTEGER NOT NULL DEFAULT 0,
    signal_csq     INTEGER,
    battery_v      REAL,
    firmware       TEXT,
    UNIQUE (trap_id, taken_at)
);
CREATE TABLE IF NOT EXISTS temperatures (
    trap_id      TEXT NOT NULL REFERENCES traps(id),
    measured_at  TEXT NOT NULL,
    celsius      REAL NOT NULL,
    PRIMARY KEY (trap_id, measured_at)
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    return conn


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def add_trap(conn: sqlite3.Connection, trap_id: str, name: str,
             lat: float | None = None, lon: float | None = None) -> str:
    """Registra una trampa y devuelve su token (solo se muestra esta vez)."""
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute(
            "INSERT INTO traps (id, name, token_hash, lat, lon) VALUES (?, ?, ?, ?, ?)",
            (trap_id, name, hash_token(token), lat, lon),
        )
    return token


def trap_for_token(conn: sqlite3.Connection, token: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM traps WHERE token_hash = ?", (hash_token(token),)).fetchone()

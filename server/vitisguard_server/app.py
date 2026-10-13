"""API que reciben las trampas y que consume el panel."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from . import db
from .detection import annotate, count_moths
from .phenology import MENDOZA, GenerationModel, daily_degree_days, season_start
from .settings import Settings

STATIC = Path(__file__).parent / "static"
# Si el total cae por debajo de esta fracción del anterior, se asume que se
# cambió el piso engomado (el técnico no siempre avisa).
LINER_DROP_RATIO = 0.5
LINER_DROP_MIN_PREVIOUS = 5


class TemperatureSample(BaseModel):
    t: datetime
    c: float = Field(ge=-30, le=70)


class CaptureMetadata(BaseModel):
    taken_at: datetime
    liner_changed: bool = False
    signal_csq: int | None = None
    battery_v: float | None = None
    firmware: str | None = None
    temperatures: list[TemperatureSample] = []


def _utc(ts: datetime) -> str:
    if ts.tzinfo is None:
        raise HTTPException(422, "los timestamps deben incluir zona horaria")
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    conn = db.connect(settings.db_path)
    model = GenerationModel()

    app = FastAPI(title="VitisGuard", version="0.1.0")
    app.state.settings = settings
    app.state.db = conn
    # TODO: proteger imágenes y panel con login antes de exponer públicamente.
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")

    def get_db() -> sqlite3.Connection:
        return conn

    def authenticated_trap(authorization: str = Header(default="")) -> sqlite3.Row:
        scheme, _, token = authorization.partition(" ")
        trap = db.trap_for_token(conn, token) if scheme.lower() == "bearer" and token else None
        if trap is None:
            raise HTTPException(401, "token inválido")
        return trap

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(STATIC / "index.html")

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.post("/api/v1/captures")
    async def upload_capture(
        metadata: str = Form(...),
        image: UploadFile = File(...),
        trap: sqlite3.Row = Depends(authenticated_trap),
        conn: sqlite3.Connection = Depends(get_db),
    ):
        try:
            meta = CaptureMetadata.model_validate_json(metadata)
        except ValidationError as e:
            raise HTTPException(422, json.loads(e.json()))
        taken_at = _utc(meta.taken_at)

        # Reintentos desde la cola del equipo: responder igual sin duplicar.
        existing = conn.execute(
            "SELECT id, count_total, count_new FROM captures WHERE trap_id = ? AND taken_at = ?",
            (trap["id"], taken_at),
        ).fetchone()
        if existing:
            return {"capture_id": existing["id"], "count_total": existing["count_total"],
                    "count_new": existing["count_new"], "duplicate": True}

        raw = await image.read(settings.max_upload_mb * 1024 * 1024 + 1)
        if len(raw) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, "imagen demasiado grande")
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(422, "la imagen no se pudo decodificar")

        result = count_moths(img)
        prev = conn.execute(
            "SELECT count_total FROM captures WHERE trap_id = ? AND taken_at < ? "
            "ORDER BY taken_at DESC LIMIT 1",
            (trap["id"], taken_at),
        ).fetchone()
        liner_changed = meta.liner_changed
        if prev is not None and not liner_changed:
            p = prev["count_total"]
            liner_changed = p >= LINER_DROP_MIN_PREVIOUS and result.count < p * LINER_DROP_RATIO
        if prev is None or liner_changed:
            count_new = result.count
        else:
            count_new = max(0, result.count - prev["count_total"])

        stem = f"{trap['id']}/{taken_at.replace(':', '')}"
        (settings.media_dir / trap["id"]).mkdir(exist_ok=True)
        (settings.media_dir / f"{stem}.jpg").write_bytes(raw)
        cv2.imwrite(str(settings.media_dir / f"{stem}_det.jpg"), annotate(img, result),
                    [cv2.IMWRITE_JPEG_QUALITY, 80])

        with conn:
            cur = conn.execute(
                "INSERT INTO captures (trap_id, taken_at, image, annotated, count_total, count_new,"
                " liner_changed, signal_csq, battery_v, firmware) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (trap["id"], taken_at, f"{stem}.jpg", f"{stem}_det.jpg", result.count, count_new,
                 int(liner_changed), meta.signal_csq, meta.battery_v, meta.firmware),
            )
            conn.executemany(
                "INSERT OR IGNORE INTO temperatures (trap_id, measured_at, celsius) VALUES (?,?,?)",
                [(trap["id"], _utc(s.t), s.c) for s in meta.temperatures],
            )
        return {"capture_id": cur.lastrowid, "count_total": result.count,
                "count_new": count_new, "liner_changed": liner_changed}

    def _trap_or_404(trap_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT id, name, lat, lon FROM traps WHERE id = ?", (trap_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "trampa inexistente")
        return row

    @app.get("/api/v1/traps")
    def list_traps():
        rows = conn.execute(
            """SELECT t.id, t.name, t.lat, t.lon, c.taken_at AS last_capture_at,
                      c.count_total AS last_count_total, c.signal_csq, c.battery_v
               FROM traps t
               LEFT JOIN captures c ON c.id = (
                   SELECT id FROM captures WHERE trap_id = t.id ORDER BY taken_at DESC LIMIT 1)
               ORDER BY t.id"""
        ).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/v1/traps/{trap_id}/captures")
    def list_captures(trap_id: str, limit: int = 30):
        _trap_or_404(trap_id)
        rows = conn.execute(
            "SELECT id, taken_at, count_total, count_new, liner_changed, signal_csq, battery_v,"
            " '/media/' || image AS image_url, '/media/' || annotated AS annotated_url"
            " FROM captures WHERE trap_id = ? ORDER BY taken_at DESC LIMIT ?",
            (trap_id, min(limit, 500)),
        ).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/v1/traps/{trap_id}/summary")
    def trap_summary(trap_id: str, today: date | None = None):
        trap = _trap_or_404(trap_id)
        today = today or datetime.now(MENDOZA).date()
        start = season_start(today)
        start_utc = datetime(start.year, start.month, start.day, tzinfo=MENDOZA).astimezone(timezone.utc)

        temps = conn.execute(
            "SELECT measured_at, celsius FROM temperatures WHERE trap_id = ? AND measured_at >= ?",
            (trap_id, start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ).fetchall()
        dd = daily_degree_days([(_parse_utc(r["measured_at"]), r["celsius"]) for r in temps])
        accumulated = sum(v for d, v in dd.items() if d <= today)

        captures = conn.execute(
            "SELECT taken_at, count_new FROM captures WHERE trap_id = ? AND taken_at >= ?",
            (trap_id, start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")),
        ).fetchall()
        weeks: dict[date, int] = {}
        for r in captures:
            d = _parse_utc(r["taken_at"]).astimezone(MENDOZA).date()
            monday = d - timedelta(days=d.weekday())
            weeks[monday] = weeks.get(monday, 0) + r["count_new"]
        this_week = weeks.get(today - timedelta(days=today.weekday()), 0)

        return {
            "trap": dict(trap),
            "season_start": start.isoformat(),
            "degree_days": round(accumulated, 1),
            "days_with_temperature": len(dd),
            "expected_flight": model.current_flight(accumulated) if dd else None,
            "weekly_captures": [{"week": w.isoformat(), "count": c} for w, c in sorted(weeks.items())],
            "this_week": this_week,
            "alert": this_week >= settings.weekly_alert_threshold,
            "alert_threshold": settings.weekly_alert_threshold,
        }

    return app


def app_from_env() -> FastAPI:
    return create_app()

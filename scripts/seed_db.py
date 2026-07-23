"""Puebla la base con nodos y un histórico de demo (para la defensa del proyecto).

Uso:
    python scripts/seed_db.py            # resetea y siembra ~30 días de datos
    python scripts/seed_db.py --days 60

Al finalizar escribe data/sim_nodes.json con los tokens de cada nodo, que usa
el simulador (scripts/simulate_node.py) para inyectar datos en vivo.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Alert, Capture, Node, Reading, generate_token  # noqa: E402
from app.alerts.engine import check_offline_nodes, evaluate_capture_threshold  # noqa: E402
from app.ingestion.service import _save_image  # noqa: E402
from scripts.trap_image import generate_trap_image  # noqa: E402

# Nodos demo en las principales zonas vitícolas de Mendoza. 'pressure' = presión de plaga.
DEMO_NODES = [
    {"node_id": "VG-001", "name": "Finca Los Álamos", "finca": "Luján de Cuyo",  "lat": -33.030, "lon": -68.882, "pressure": 0.3},
    {"node_id": "VG-002", "name": "Viñedo Agrelo",    "finca": "Agrelo",          "lat": -33.132, "lon": -68.900, "pressure": 1.6},
    {"node_id": "VG-003", "name": "Bodega Maipú Este", "finca": "Maipú",          "lat": -32.980, "lon": -68.790, "pressure": 0.5},
    {"node_id": "VG-004", "name": "Vista Flores",     "finca": "Valle de Uco",    "lat": -33.680, "lon": -69.130, "pressure": 1.9},
    {"node_id": "VG-005", "name": "San Rafael Norte", "finca": "San Rafael",      "lat": -34.550, "lon": -68.400, "pressure": 0.2},
    {"node_id": "VG-006", "name": "Tupungato Alto",   "finca": "Tupungato",       "lat": -33.370, "lon": -69.150, "pressure": 0.6},
]


def seed(days: int) -> None:
    rnd = random.Random(2026)
    now = datetime.now(timezone.utc)

    db.drop_all()
    db.create_all()

    sim_nodes = []
    for spec in DEMO_NODES:
        token = generate_token()
        node = Node(
            node_id=spec["node_id"], name=spec["name"], finca=spec["finca"],
            latitude=spec["lat"], longitude=spec["lon"], crop="Vid",
            api_token=token, install_date=now - timedelta(days=days + 5),
            last_seen=now,
        )
        db.session.add(node)
        db.session.flush()  # asigna node.id

        # --- lecturas ambientales (cada 2 h) ---
        for d in range(days, -1, -1):
            for hour in range(0, 24, 2):
                ts = (now - timedelta(days=d)).replace(hour=hour, minute=0, second=0, microsecond=0)
                if ts > now:
                    continue
                daily = math.sin((hour - 6) / 24 * 2 * math.pi)
                temp = round(19 + 8 * daily + rnd.uniform(-1.5, 1.5), 1)
                hum = round(55 - 18 * daily + rnd.uniform(-4, 4), 1)
                batt = round(3.9 + 0.35 * max(0, daily) + rnd.uniform(-0.05, 0.05), 2)
                db.session.add(Reading(node_id=node.id, timestamp=ts, temperature=temp,
                                       humidity=hum, battery_v=batt, source="seed"))

        # --- capturas diarias (con imagen) ---
        for d in range(days, -1, -1):
            ts = (now - timedelta(days=d)).replace(hour=7, minute=30, second=0, microsecond=0)
            if ts > now:
                continue
            base = spec["pressure"] * (0.5 + d_ramp(d, days))
            count = max(0, int(rnd.gauss(base, 0.8)))
            img = generate_trap_image(num_moths=count, seed=rnd.randint(0, 10**6))
            rel = _save_image(node.node_id, ts, img)
            db.session.add(Capture(
                node_id=node.id, timestamp=ts, image_path=rel,
                detection_count=count,
                species="Lobesia botrana" if count else None,
                confidence=round(rnd.uniform(0.72, 0.95), 2) if count else None,
                status="processed",
            ))

        node.battery_v = batt
        sim_nodes.append({"node_id": spec["node_id"], "token": token,
                          "lat": spec["lat"], "lon": spec["lon"]})

    db.session.commit()

    # Un nodo "offline" para demostrar la alerta correspondiente.
    offline = Node.query.filter_by(node_id="VG-005").first()
    offline.last_seen = now - timedelta(hours=12)
    db.session.commit()

    # Disparar el motor de alertas sobre los datos sembrados.
    for node in Node.query.all():
        evaluate_capture_threshold(node)
    check_offline_nodes()

    # Persistir credenciales para el simulador.
    out = ROOT / "data" / "sim_nodes.json"
    out.write_text(json.dumps(sim_nodes, indent=2))

    _summary(out)


def d_ramp(d: int, days: int) -> float:
    """Rampa temporal: más presión de plaga cerca del presente (temporada activa)."""
    return 1.0 - d / max(days, 1)


def _summary(sim_path: Path) -> None:
    print("\n=== VitisGuard seed ===")
    print(f"Nodos:    {Node.query.count()}")
    print(f"Lecturas: {Reading.query.count()}")
    print(f"Capturas: {Capture.query.count()}")
    print(f"Alertas:  {Alert.query.count()} (abiertas: {Alert.query.filter_by(acknowledged=False).count()})")
    print(f"Tokens de nodos -> {sim_path.relative_to(ROOT)}")
    print("Listo. Arrancá el server con:  python run.py\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        seed(args.days)


if __name__ == "__main__":
    main()

"""Simulador de nodos de campo VitisGuard (para demostrar el sistema sin hardware).

Emula uno o varios nodos que capturan una imagen de trampa + DHT22 y los envían
al servidor por HTTP o por MQTT. Lee los tokens desde data/sim_nodes.json (generado
por scripts/seed_db.py).

Ejemplos:
    python scripts/seed_db.py                        # primero sembrar (crea tokens)
    python scripts/simulate_node.py --transport http --interval 5
    python scripts/simulate_node.py --transport http --burst --node VG-001
    python scripts/simulate_node.py --transport mqtt --interval 10
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.trap_image import generate_trap_image  # noqa: E402

NODES_FILE = ROOT / "data" / "sim_nodes.json"


def load_nodes(only: str | None):
    if not NODES_FILE.exists():
        sys.exit("No existe data/sim_nodes.json. Corré primero:  python scripts/seed_db.py")
    nodes = json.loads(NODES_FILE.read_text())
    if only:
        nodes = [n for n in nodes if n["node_id"] == only]
        if not nodes:
            sys.exit(f"Nodo {only} no encontrado en {NODES_FILE.name}")
    return nodes


def sample_env() -> tuple[float, float, float]:
    hour = datetime.now().hour
    daily = math.sin((hour - 6) / 24 * 2 * math.pi)
    temp = round(19 + 8 * daily + random.uniform(-1.5, 1.5), 1)
    hum = round(55 - 18 * daily + random.uniform(-4, 4), 1)
    batt = round(3.9 + 0.35 * max(0, daily) + random.uniform(-0.05, 0.05), 2)
    return temp, hum, batt


def sample_count(burst: bool) -> int:
    if burst:
        return random.randint(1, 3)
    return max(0, int(random.gauss(0.7, 0.9)))


# --------------------------------------------------------------------------- #
# Transporte HTTP
# --------------------------------------------------------------------------- #
def send_http(server: str, node: dict, burst: bool) -> None:
    temp, hum, batt = sample_env()
    count = sample_count(burst)
    img = generate_trap_image(num_moths=count, seed=random.randint(0, 10**6))
    data = {
        "node_id": node["node_id"],
        "temperature": temp, "humidity": hum, "battery_v": batt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    resp = requests.post(
        server.rstrip("/") + "/api/ingest",
        headers={"Authorization": f"Bearer {node['token']}"},
        data={"data": json.dumps(data)},
        files={"image": ("trap.jpg", img, "image/jpeg")},
        timeout=20, verify=False,
    )
    tag = "OK " if resp.ok else "ERR"
    print(f"[HTTP {tag}] {node['node_id']}  T={temp}°C H={hum}% moths~{count}  -> {resp.status_code}")


# --------------------------------------------------------------------------- #
# Transporte MQTT
# --------------------------------------------------------------------------- #
def make_mqtt_client(args):
    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if args.mqtt_user:
        client.username_pw_set(args.mqtt_user, args.mqtt_password)
    if args.mqtt_tls:
        client.tls_set(ca_certs=args.mqtt_ca)
        if args.mqtt_insecure:
            client.tls_insecure_set(True)
    client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
    client.loop_start()
    return client


def send_mqtt(client, base: str, node: dict, burst: bool) -> None:
    temp, hum, batt = sample_env()
    count = sample_count(burst)
    img = generate_trap_image(num_moths=count, seed=random.randint(0, 10**6))
    env = {"temperature": temp, "humidity": hum, "battery_v": batt}
    nid = node["node_id"]
    client.publish(f"{base}/{nid}/env", json.dumps(env), qos=0)
    client.publish(f"{base}/{nid}/image", base64.b64encode(img).decode(), qos=0)
    print(f"[MQTT] {nid}  T={temp}°C H={hum}% moths~{count}  -> {base}/{nid}/*")


# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description="Simulador de nodos VitisGuard")
    p.add_argument("--transport", choices=["http", "mqtt"], default="http")
    p.add_argument("--server", default="http://127.0.0.1:5000")
    p.add_argument("--node", help="Simular solo este node_id")
    p.add_argument("--interval", type=float, default=5.0, help="segundos entre ciclos")
    p.add_argument("--cycles", type=int, default=0, help="0 = infinito")
    p.add_argument("--once", action="store_true", help="un solo ciclo y termina")
    p.add_argument("--burst", action="store_true",
                   help="capturas altas repetidas para disparar la alerta por umbral")
    # MQTT
    p.add_argument("--mqtt-host", default="127.0.0.1")
    p.add_argument("--mqtt-port", type=int, default=8883)
    p.add_argument("--mqtt-base", default="vitisguard")
    p.add_argument("--mqtt-tls", action="store_true", default=True)
    p.add_argument("--mqtt-insecure", action="store_true",
                   help="no validar el hostname del cert (dev)")
    p.add_argument("--mqtt-ca", default=str(ROOT / "certs" / "ca.crt"))
    p.add_argument("--mqtt-user", default="")
    p.add_argument("--mqtt-password", default="")
    args = p.parse_args()

    if args.transport == "http":
        requests.packages.urllib3.disable_warnings()  # silenciar warning de TLS adhoc

    nodes = load_nodes(args.node)
    print(f"Simulando {len(nodes)} nodo(s) por {args.transport.upper()} "
          f"(intervalo {args.interval}s, {'burst' if args.burst else 'normal'})")

    mqtt_client = make_mqtt_client(args) if args.transport == "mqtt" else None

    cycles = 1 if args.once else args.cycles
    n = 0
    try:
        while True:
            for node in nodes:
                try:
                    if args.transport == "http":
                        send_http(args.server, node, args.burst)
                    else:
                        send_mqtt(mqtt_client, args.mqtt_base, node, args.burst)
                except Exception as exc:  # noqa: BLE001
                    print(f"[ERROR] {node['node_id']}: {exc}")
            n += 1
            if cycles and n >= cycles:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nDetenido.")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()


if __name__ == "__main__":
    main()

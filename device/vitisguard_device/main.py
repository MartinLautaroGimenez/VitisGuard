"""Punto de entrada. Lo disparan los timers de systemd:

  vitisguard sample   cada hora: registra temperatura (no usa el módem)
  vitisguard run      una vez por día: foto + subida de todo lo pendiente
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import __version__, hardware, modem
from .config import DEFAULT_PATH, Config
from .outbox import Item, Outbox

log = logging.getLogger("vitisguard")


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def cmd_sample(cfg: Config) -> int:
    celsius = hardware.read_ds18b20()
    if celsius is None:
        log.warning("sin lectura de temperatura")
        return 1
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    with cfg.temperature_log.open("a") as f:
        f.write(json.dumps({"t": now_utc().isoformat(), "c": celsius}) + "\n")
    log.info("temperatura %.2f °C", celsius)
    return 0


def take_temperatures(cfg: Config) -> list[dict]:
    """Consume el log de temperaturas; pasan a viajar dentro de la captura."""
    if not cfg.temperature_log.exists():
        return []
    samples = []
    for line in cfg.temperature_log.read_text().splitlines():
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            log.warning("línea de temperatura corrupta descartada: %r", line)
    cfg.temperature_log.unlink()
    return samples


def cmd_capture(cfg: Config, outbox: Outbox) -> Item:
    taken_at = now_utc()
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "capture.jpg"
        with hardware.gpio_on(cfg.camera.led_gpio, settle_s=cfg.camera.warmup_s):
            hardware.capture_still(img, cfg.camera.width, cfg.camera.height)
        metadata = {
            "taken_at": taken_at.isoformat(),
            "firmware": __version__,
            "liner_changed": cfg.liner_flag.exists(),
            "temperatures": take_temperatures(cfg),
        }
        item = outbox.put(taken_at.strftime("%Y%m%dT%H%M%SZ"), img, metadata)
    cfg.liner_flag.unlink(missing_ok=True)
    log.info("captura en cola: %s", item.image.name)
    return item


def make_sender(cfg: Config, signal_csq: int | None):
    url = cfg.server_url.rstrip("/") + "/api/v1/captures"
    headers = {"Authorization": f"Bearer {cfg.token}"}

    def send(item: Item) -> bool:
        meta = item.metadata
        if signal_csq is not None:
            meta["signal_csq"] = signal_csq
        try:
            with item.image.open("rb") as f:
                r = requests.post(url, headers=headers, timeout=cfg.upload_timeout_s,
                                  data={"metadata": json.dumps(meta)},
                                  files={"image": (item.image.name, f, "image/jpeg")})
        except requests.RequestException as e:
            log.error("fallo de red subiendo %s: %s", item.image.name, e)
            return False
        if r.ok:
            log.info("subida %s: %s", item.image.name, r.json())
            return True
        log.error("servidor rechazó %s: %s %s", item.image.name, r.status_code, r.text[:200])
        return False

    return send


def cmd_upload(cfg: Config, outbox: Outbox) -> int:
    if not outbox.pending():
        return 0
    with hardware.gpio_on(cfg.modem.power_gpio):
        if not modem.wait_for_server(cfg.server_url, cfg.modem.connect_timeout_s):
            return 1
        csq = modem.signal_quality(cfg.modem.at_port, cfg.modem.baud)
        sent = outbox.flush(make_sender(cfg, csq))
    remaining = len(outbox.pending())
    log.info("subidas %d, pendientes %d", sent, remaining)
    return 0 if remaining == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vitisguard")
    parser.add_argument("--config", type=Path, default=DEFAULT_PATH)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("command", choices=["sample", "capture", "upload", "run"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = Config.load(args.config)
    if args.command == "sample":
        return cmd_sample(cfg)
    outbox = Outbox(cfg.outbox_dir, cfg.outbox_max_items)
    if args.command in ("capture", "run"):
        cmd_sample(cfg)  # una muestra más justo antes de la foto
        cmd_capture(cfg, outbox)
    if args.command in ("upload", "run"):
        return cmd_upload(cfg, outbox)
    return 0


if __name__ == "__main__":
    sys.exit(main())

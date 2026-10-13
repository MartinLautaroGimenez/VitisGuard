"""Cámara, LED y alimentación del módem. Todo degrada a no-op fuera de la Pi."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)

try:
    from gpiozero import OutputDevice
except ImportError:  # desarrollo en PC
    OutputDevice = None


@contextmanager
def gpio_on(pin: int | None, settle_s: float = 0.0):
    """Mantiene un pin en alto durante el bloque (LED, MOSFET del módem)."""
    if pin is None or OutputDevice is None:
        yield
        return
    dev = OutputDevice(pin, active_high=True, initial_value=False)
    try:
        dev.on()
        time.sleep(settle_s)
        yield
    finally:
        dev.off()
        dev.close()


def capture_still(path: Path, width: int, height: int) -> None:
    """Saca una foto con rpicam-still (Bookworm) o libcamera-still (Bullseye)."""
    binary = shutil.which("rpicam-still") or shutil.which("libcamera-still")
    if binary is None:
        raise RuntimeError("no se encontró rpicam-still ni libcamera-still")
    cmd = [binary, "--nopreview", "--immediate", "-t", "1",
           "--width", str(width), "--height", str(height),
           "--quality", "90", "-o", str(path)]
    log.debug("capturando: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)


def read_ds18b20(base: Path = Path("/sys/bus/w1/devices")) -> float | None:
    """Lee el primer DS18B20 del bus 1-Wire (dtoverlay=w1-gpio)."""
    for sensor in sorted(base.glob("28-*")):
        try:
            lines = (sensor / "w1_slave").read_text().splitlines()
        except OSError:
            continue
        if len(lines) == 2 and lines[0].endswith("YES") and "t=" in lines[1]:
            milli = int(lines[1].split("t=")[1])
            if milli != 85000:  # 85 °C es el valor de power-on, no una lectura
                return milli / 1000
    return None

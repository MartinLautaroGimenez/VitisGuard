"""Cámara, LED, sensores y alimentación del módem. Degrada a no-op fuera de la Pi."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Climate:
    celsius: float
    humidity: float | None = None


def read_dht22(base: Path = Path("/sys/bus/iio/devices"), retries: int = 5,
               wait_s: float = 2.5) -> Climate | None:
    """Lee un DHT22 a través del driver del kernel (dtoverlay=dht11, sirve para DHT22).

    El kernel resuelve los tiempos del protocolo; leerlo desde Python en una
    Zero W de un núcleo falla seguido. Aun así hay lecturas con EIO/ETIMEDOUT,
    por eso se reintenta respetando los 2 s mínimos entre lecturas del sensor.
    """
    for attempt in range(retries):
        for dev in sorted(base.glob("iio:device*")):
            try:
                if (dev / "name").read_text().strip() != "dht11":
                    continue
                celsius = int((dev / "in_temp_input").read_text()) / 1000
                humidity = int((dev / "in_humidityrelative_input").read_text()) / 1000
            except (OSError, ValueError):
                break
            if -40 <= celsius <= 80 and 0 <= humidity <= 100:
                return Climate(celsius, humidity)
        if attempt + 1 < retries:
            time.sleep(wait_s)
    return None


def read_climate(sensor: str) -> Climate | None:
    if sensor == "dht22":
        return read_dht22()
    if sensor == "ds18b20":
        celsius = read_ds18b20()
        return None if celsius is None else Climate(celsius)
    raise ValueError(f"sensor desconocido: {sensor}")


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

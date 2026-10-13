"""Diagnóstico del módem 4G por comandos AT y espera de conectividad.

La conexión de datos en sí la maneja el sistema operativo (ModemManager +
NetworkManager, o el modo RNDIS/ECM del módulo). Acá solo se consulta la
señal para reportarla y se espera a que haya ruta al servidor.
"""

from __future__ import annotations

import logging
import re
import socket
import time
from urllib.parse import urlparse

log = logging.getLogger(__name__)

_CSQ = re.compile(r"\+CSQ:\s*(\d+),\s*(\d+)")


def parse_csq(response: str) -> int | None:
    """'+CSQ: 18,99' -> 18. 99 significa desconocido."""
    m = _CSQ.search(response)
    if not m or m.group(1) == "99":
        return None
    return int(m.group(1))


def at_command(port: str, command: str, baud: int = 115200, timeout: float = 3.0) -> str:
    import serial  # pyserial; import diferido para poder testear sin hardware

    with serial.Serial(port, baud, timeout=timeout) as ser:
        ser.reset_input_buffer()
        ser.write((command + "\r").encode())
        deadline = time.monotonic() + timeout
        out = b""
        while time.monotonic() < deadline:
            out += ser.read(ser.in_waiting or 1)
            if b"OK\r\n" in out or b"ERROR" in out:
                break
        return out.decode(errors="replace")


def signal_quality(port: str | None, baud: int = 115200) -> int | None:
    if not port:
        return None
    try:
        return parse_csq(at_command(port, "AT+CSQ", baud))
    except Exception as e:  # el reporte de señal nunca debe frenar la subida
        log.warning("no se pudo leer CSQ: %s", e)
        return None


def wait_for_server(url: str, timeout_s: int, poll_s: float = 5.0) -> bool:
    """Espera hasta que se pueda abrir un TCP al servidor."""
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            with socket.create_connection((parsed.hostname, port), timeout=10):
                return True
        except OSError as e:
            if time.monotonic() >= deadline:
                log.error("sin conectividad a %s: %s", parsed.hostname, e)
                return False
            time.sleep(poll_s)

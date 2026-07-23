"""VitisGuard — firmware de REFERENCIA del nodo de campo (Raspberry Pi Zero 2 W).

Captura una imagen de la trampa (picamera2) + temperatura/humedad (DHT22) y las envía
al servidor por HTTPS a través del módulo celular SIM800L (GSM/GPRS, comandos AT).

⚠️  Es código de REFERENCIA: corre en la Raspberry con el hardware conectado; no es
    testeable en una PC común. Para probar el servidor sin hardware usá el simulador
    (scripts/simulate_node.py), que emula exactamente este envío.

Dependencias en la Pi (Raspberry Pi OS Lite):
    sudo apt install python3-picamera2
    pip install adafruit-circuitpython-dht pyserial requests

Config por variables de entorno (o editá los valores por defecto abajo):
    VG_SERVER, VG_NODE_ID, VG_TOKEN, VG_SERIAL_PORT, VG_APN, VG_INTERVAL
"""
from __future__ import annotations

import base64
import json
import os
import time
from datetime import datetime, timezone

# --- Configuración ---------------------------------------------------------- #
SERVER = os.environ.get("VG_SERVER", "https://tu-servidor.example.com")
NODE_ID = os.environ.get("VG_NODE_ID", "VG-001")
TOKEN = os.environ.get("VG_TOKEN", "PEGAR_TOKEN_DEL_NODO")
SERIAL_PORT = os.environ.get("VG_SERIAL_PORT", "/dev/ttyS0")
BAUD = int(os.environ.get("VG_BAUD", "115200"))
APN = os.environ.get("VG_APN", "internet.movil")          # APN de la operadora
INTERVAL = int(os.environ.get("VG_INTERVAL", "3600"))      # segundos entre capturas
DHT_PIN = os.environ.get("VG_DHT_PIN", "D4")


# --- Sensores --------------------------------------------------------------- #
def capture_image() -> bytes:
    """Foto JPEG de la trampa con la cámara CSI (picamera2)."""
    from picamera2 import Picamera2
    import io

    cam = Picamera2()
    cam.configure(cam.create_still_configuration(main={"size": (1640, 1232)}))
    cam.start()
    time.sleep(2)  # estabilizar exposición
    buf = io.BytesIO()
    cam.capture_file(buf, format="jpeg")
    cam.stop()
    cam.close()
    return buf.getvalue()


def read_dht22() -> tuple[float | None, float | None]:
    """Temperatura (°C) y humedad (%) del DHT22."""
    try:
        import adafruit_dht
        import board

        pin = getattr(board, DHT_PIN)
        sensor = adafruit_dht.DHT22(pin)
        temp = sensor.temperature
        hum = sensor.humidity
        sensor.exit()
        return temp, hum
    except Exception as exc:  # noqa: BLE001 - un sensor no debe frenar el envío
        print(f"[DHT22] lectura fallida: {exc}")
        return None, None


# --- Módulo celular SIM800L (comandos AT) ----------------------------------- #
class SIM800L:
    def __init__(self, port: str, baud: int):
        import serial
        self.ser = serial.Serial(port, baud, timeout=10)

    def at(self, cmd: str, wait: float = 1.0) -> str:
        self.ser.write((cmd + "\r\n").encode())
        time.sleep(wait)
        return self.ser.read(self.ser.in_waiting or 1).decode(errors="ignore")

    def gprs_up(self, apn: str) -> None:
        self.at("AT")
        self.at("AT+CFUN=1", 2)
        self.at("AT+CGATT=1", 2)
        self.at('AT+SAPBR=3,1,"Contype","GPRS"')
        self.at(f'AT+SAPBR=3,1,"APN","{apn}"')
        self.at("AT+SAPBR=1,1", 3)   # abrir portadora GPRS

    def http_post_json(self, url: str, payload: dict, token: str) -> str:
        body = json.dumps(payload)
        self.at("AT+HTTPINIT")
        self.at("AT+HTTPPARA=\"CID\",1")
        self.at(f'AT+HTTPPARA="URL","{url}"')
        self.at('AT+HTTPPARA="CONTENT","application/json"')
        self.at(f'AT+HTTPPARA="USERDATA","Authorization: Bearer {token}"')
        self.at("AT+HTTPSSL=1")                       # HTTPS
        self.at(f"AT+HTTPDATA={len(body)},10000", 1)
        self.at(body, 2)
        resp = self.at("AT+HTTPACTION=1", 8)          # 1 = POST
        self.at("AT+HTTPTERM")
        return resp

    def close(self) -> None:
        self.at("AT+SAPBR=0,1")
        self.ser.close()


# --- Ciclo principal -------------------------------------------------------- #
def build_payload() -> dict:
    image = capture_image()
    temp, hum = read_dht22()
    return {
        "node_id": NODE_ID,
        "temperature": temp,
        "humidity": hum,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "image_b64": base64.b64encode(image).decode(),
    }


def main() -> None:
    print(f"VitisGuard nodo {NODE_ID} -> {SERVER} cada {INTERVAL}s")
    while True:
        try:
            modem = SIM800L(SERIAL_PORT, BAUD)
            modem.gprs_up(APN)
            payload = build_payload()
            resp = modem.http_post_json(f"{SERVER}/api/ingest", payload, TOKEN)
            print(f"[{datetime.now():%H:%M:%S}] enviado. Respuesta modem: {resp.strip()[:80]}")
            modem.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] ciclo fallido: {exc}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

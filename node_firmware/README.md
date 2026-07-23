# VitisGuard — Firmware del nodo de campo (referencia)

Código que corre en la **Raspberry Pi Zero 2 W** del nodo. Captura la imagen de la
trampa y el DHT22, y los envía al servidor por HTTPS a través del **SIM800L** (GSM/GPRS).

> ⚠️ Es **referencia**: requiere el hardware conectado (cámara CSI, DHT22, SIM800L con
> SIM y cobertura). No se prueba en una PC. Para validar el servidor sin hardware usá
> `scripts/simulate_node.py`, que emula exactamente este mismo envío.

## Hardware
- Raspberry Pi Zero 2 W (Raspberry Pi OS Lite)
- Módulo de cámara CSI (IMX219 / Camera Module 3)
- Sensor DHT22 (temperatura/humedad) en un GPIO (por defecto D4)
- Módulo SIM800L (GSM/GPRS) por UART (`/dev/ttyS0`), con SIM y antena
- Alimentación solar + batería (fuera del alcance de este script)

## Instalación en la Pi
```bash
sudo apt install python3-picamera2
pip install adafruit-circuitpython-dht pyserial requests
```

## Configuración (variables de entorno)
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `VG_SERVER` | URL del servidor | `https://vitisguard.midominio.com` |
| `VG_NODE_ID` | ID del nodo | `VG-001` |
| `VG_TOKEN` | Token del nodo (lo da el servidor) | `a1b2c3...` |
| `VG_SERIAL_PORT` | Puerto del SIM800L | `/dev/ttyS0` |
| `VG_APN` | APN de la operadora | `internet.movil` |
| `VG_INTERVAL` | Segundos entre capturas | `3600` |

## Ejecución
```bash
VG_TOKEN=xxxx VG_NODE_ID=VG-001 python3 vitisguard_node.py
```
Para producción, correrlo como servicio `systemd` para que reinicie solo.

## Nota sobre el envío
El nodo hace `POST /api/ingest` con **JSON** (`node_id`, `temperature`, `humidity`,
`timestamp`, `image_b64`) porque enviar `multipart` por comandos AT del SIM800L es
poco práctico. El servidor acepta tanto JSON+base64 como `multipart/form-data`.

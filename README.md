# 🍇 VitisGuard

Sistema IoT de bajo costo para el **monitoreo de la polilla de la vid** (*Lobesia botrana*)
en viñedos de Mendoza. Este repositorio contiene **toda la capa informática de servidor**
consolidada en **Python + Flask**: ingesta de datos, almacenamiento, dashboard web,
motor de alertas y el microservicio de clasificación por IA.

> Proyecto REM · Taller AeroGlobETec · Escuela Técnica de la Universidad de Mendoza · 2026

---

## Arquitectura

```
 Nodo de campo (Raspberry Pi + cámara + DHT22 + SIM800L, solar)
        │  HTTPS (JSON/base64 o multipart)     │  MQTT/TLS (telemetría + imagen b64)
        ▼                                       ▼
 ┌─────────────────────────  SERVIDOR FLASK  ─────────────────────────┐
 │  /api/ingest (HTTP)   +   suscriptor MQTT   →  pipeline único       │
 │  → guarda imagen → Reading → [Microservicio IA] → Capture           │
 │  → motor de alertas (umbral / offline) → notificador                │
 │  Dashboard (mapa, gráficos, galería, reportes) + API JSON           │
 │  SQLite (data/vitisguard.db) + storage/images/                      │
 └─────────────────────────────────────────────────────────────────────┘
        ▲
 Microservicio IA (FastAPI) — detector CV (ya) / YOLO11 (entrenable)
```

Componentes:
- **Ingesta dual**: endpoint HTTP (`/api/ingest`) **y** suscriptor MQTT (Mosquitto/TLS),
  ambos convergen en el mismo pipeline (`app/ingestion/service.py`).
- **Almacenamiento**: SQLite vía SQLAlchemy; imágenes en `storage/images/`.
- **Dashboard**: panel con KPIs, mapa de nodos (Leaflet), series temporales (Chart.js),
  galería de capturas y exportación de reportes CSV. Librerías bundleadas → funciona offline.
- **Alertas**: umbral de capturas por semana (default ≥5) y nodos sin reporte; notifica por
  log/dashboard (activo) o email/WhatsApp (listos para activar).
- **IA**: microservicio FastAPI aparte (`ai_service/`) con backend CV inmediato y camino a
  YOLO11 entrenado. El core Flask lo consume por HTTP y degrada si no está disponible.

---

## Requisitos
- Python 3.11+ (probado en 3.14) para el servidor Flask.
- `mosquitto` (opcional, solo para la vía MQTT): `sudo pacman -S mosquitto` / `apt install mosquitto`.
- Para el backend YOLO real: Python 3.11/3.12 recomendado (por torch).

---

## Puesta en marcha (servidor + demo, sin hardware)

```bash
# 1) Entorno e instalación
python -m venv .venv
source .venv/bin/activate            # fish: source .venv/bin/activate.fish
pip install -r requirements.txt
cp .env.example .env                 # ajustá si querés

# 2) Datos de demostración (nodos + histórico + alertas)
python scripts/seed_db.py

# 3) Levantar el servidor
python run.py                        # http://localhost:5000
```

Abrí **http://localhost:5000** → deberías ver el panel con el mapa de nodos de Mendoza,
gráficos poblados, galería y alertas.

### Inyectar datos en vivo (simulador de nodo)
En otra terminal (con el venv activado):
```bash
# Envío periódico por HTTP de todos los nodos
python scripts/simulate_node.py --transport http --interval 5

# Ráfaga en un nodo para disparar la alerta por umbral
python scripts/simulate_node.py --transport http --burst --node VG-001 --cycles 6 --interval 1
```

### Activar la IA (opcional, recomendado para la demo)
```bash
cd ai_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # backend CV, cuenta polillas ya
uvicorn main:app --port 8001
```
Con la IA corriendo, las nuevas capturas muestran conteo, especie e imagen anotada.
Para el modelo YOLO11 entrenado, ver [ai_service/README.md](ai_service/README.md).

### Activar la vía MQTT (opcional)
```bash
bash mosquitto/gen_certs.sh                       # certificados TLS de dev
mosquitto -c mosquitto/mosquitto.conf -v          # broker en :8883
# En .env: MQTT_ENABLED=true   (y reiniciar run.py)
python scripts/simulate_node.py --transport mqtt --mqtt-insecure --interval 8
```

---

## Estructura del proyecto
```
app/            core Flask (ingesta, modelos, alertas, dashboard, API)
ai_service/     microservicio de IA (FastAPI + detector CV/YOLO11)
scripts/        seed_db.py (histórico demo) + simulate_node.py (simulador)
node_firmware/  firmware de referencia para la Raspberry Pi (SIM800L)
mosquitto/      config del broker + generación de certificados TLS
tests/          pruebas de ingesta y alertas
```

## Tests
```bash
pytest
```

## Configuración
Todas las opciones se ajustan por variables de entorno (ver [.env.example](.env.example)):
umbrales de alerta, backend de notificación, URL de la IA, parámetros MQTT y de la base.

## Endpoints principales
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/ingest` | Ingesta del nodo (multipart o JSON+base64, auth Bearer) |
| GET | `/api/stats/overview` | KPIs del panel |
| GET | `/api/nodes` · `/api/nodes/<id>/readings` | Nodos y series |
| GET | `/api/captures` · `/api/alerts` | Capturas y alertas |
| GET | `/reports/export.csv` | Exportación CSV |

---

Licencia educativa — ETec UM.

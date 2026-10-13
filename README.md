# VitisGuard

Trampas delta conectadas para el monitoreo de **Lobesia botrana** (polilla de la vid) en Mendoza.

Cada trampa es una trampa delta estándar con feromona y piso engomado, más una
caja estanca arriba con una Raspberry Pi Zero W, una cámara OV5647 mirando el
piso, un LED y un módem 4G. Una vez por día saca una
foto, la sube, y el servidor cuenta las polillas, calcula cuántas son nuevas y
acumula grados-día para estimar en qué vuelo está la plaga.

El objetivo es que el monitoreo que hoy se hace recorriendo trampas a mano
(ISCAMEN, técnicos de fincas) tenga datos **diarios**, en lugar de semanales,
sin ir al campo.

```
┌──────────── trampa ────────────┐            ┌──────────── servidor ─────────────┐
│ DHT22 ────┐                    │            │                                   │
│ cámara ───┤ Pi Zero ── 4G ─────┼── HTTPS ──▶│ FastAPI ─▶ conteo (YOLO11n)       │
│ LED ──────┘   cola en SD       │            │        ─▶ SQLite (capturas, °C)   │
│ panel solar + batería          │            │        ─▶ grados-día / alertas    │
└────────────────────────────────┘            │ panel web                         │
                                              └───────────────────────────────────┘
```

## Qué hay en el repo

| Carpeta   | Qué es |
|-----------|--------|
| `device/` | Software de la trampa: foto con LED, temperatura horaria, cola persistente, subida por 4G. Timers de systemd. |
| `server/` | API + conteo de polillas + grados-día + panel web. |
| `docs/`   | [Hardware y BOM](docs/hardware.md), [gabinete](docs/gabinete.md), [modelo](docs/modelo.md), [ideas y contexto ISCAMEN](docs/iscamen.md). |

## Cómo funciona

**En la trampa** (`device/`)
- `vitisguard sample` cada hora: lee el DHT22 (temperatura y humedad) y lo guarda localmente. No prende el módem.
- `vitisguard run` una vez por día (10:00): prende el LED, saca la foto, la guarda en
  la cola junto con las temperaturas acumuladas, prende el módem, espera red y sube
  todo lo pendiente. Si no hay señal, queda en la cola para el día siguiente.
- El módem se alimenta por un MOSFET y solo está prendido durante la subida:
  es el consumidor más grande (picos de 2 A).

**En el servidor** (`server/`)
- `POST /api/v1/captures`: recibe foto + metadatos con token por trampa. Es
  idempotente (los reintentos no duplican).
- Cuenta polillas con un detector **YOLO11n entrenado para Lobesia**
  ([detalles y pendientes](docs/modelo.md)). Sin ultralytics instalado, cae a
  un conteo clásico con OpenCV que cuenta cualquier mancha oscura.
- Las trampas **acumulan** polillas: lo que importa es `count_new` = total de hoy −
  total de ayer. Si el total cae fuerte, se asume cambio de piso engomado.
- Grados-día base 10 °C / corte 30 °C desde el 1/7, integrando las muestras horarias.
- Alerta cuando las capturas nuevas de la semana superan un umbral configurable.

## Arranque rápido (desarrollo)

```bash
# Servidor
cd server
pip install -e '.[dev,yolo]'   # sin ",yolo" usa el conteo clásico
pytest
export VG_DATA_DIR=./data
vitisguard-admin add-trap trampa-001 --name "Finca de prueba" --lat -33.03 --lon -68.88
uvicorn --factory vitisguard_server.app:app_from_env --reload
# panel en http://localhost:8000, API en http://localhost:8000/docs

# Trampa
cd device
pip install -e '.[dev]'
pytest
```

En la Raspberry: `sudo ./device/install.sh` y completar `/etc/vitisguard/config.yaml`
con el token que imprimió `vitisguard-admin`.

## Estado y próximos pasos

- [x] Software de la trampa con cola offline
- [x] API, grados-día, panel básico
- [x] Detector YOLO11n integrado (primera versión)
- [ ] Armar el primer prototipo físico (gabinete estanco) y juntar fotos reales
- [ ] Validar y reentrenar el modelo con fotos del dispositivo real
- [ ] Calibrar umbrales de vuelos y alertas con series históricas de ISCAMEN
- [ ] Login en el panel, mapa de trampas, alertas por WhatsApp/Telegram
- [ ] Telemetría de batería (INA219) y actualización remota del software

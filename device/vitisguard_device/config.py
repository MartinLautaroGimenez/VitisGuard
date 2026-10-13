from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_PATH = Path("/etc/vitisguard/config.yaml")


@dataclass
class CameraConfig:
    width: int = 2028
    height: int = 1520
    # GPIO (BCM) del MOSFET que prende el anillo LED; None = sin LED.
    led_gpio: int | None = 17
    warmup_s: float = 1.0


@dataclass
class ModemConfig:
    # Puerto AT del módulo (SIM7600/A7670 por USB expone varios ttyUSB).
    at_port: str | None = "/dev/ttyUSB2"
    baud: int = 115200
    # GPIO que corta la alimentación del módem; None = siempre encendido.
    power_gpio: int | None = 27
    # Tiempo máximo para que el módem registre en la red y haya ruta al servidor.
    connect_timeout_s: int = 120


@dataclass
class Config:
    trap_id: str
    token: str
    server_url: str
    data_dir: Path = Path("/var/lib/vitisguard")
    camera: CameraConfig = field(default_factory=CameraConfig)
    modem: ModemConfig = field(default_factory=ModemConfig)
    # Máximo de capturas en cola: protege la SD si el equipo pasa semanas sin señal.
    outbox_max_items: int = 60
    upload_timeout_s: int = 90

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "Config":
        raw = yaml.safe_load(Path(path).read_text()) or {}
        camera = CameraConfig(**raw.pop("camera", {}) or {})
        modem = ModemConfig(**raw.pop("modem", {}) or {})
        if "data_dir" in raw:
            raw["data_dir"] = Path(raw["data_dir"])
        return cls(camera=camera, modem=modem, **raw)

    @property
    def outbox_dir(self) -> Path:
        return self.data_dir / "outbox"

    @property
    def temperature_log(self) -> Path:
        return self.data_dir / "temperatures.jsonl"

    @property
    def liner_flag(self) -> Path:
        return self.data_dir / "liner_changed"

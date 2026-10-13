from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = Path(__file__).resolve().parent.parent / "models" / "lobesia_yolo11n_20261010.pt"


def _model_from_env() -> Path | None:
    value = os.environ.get("VG_MODEL", "")
    if value == "classic":
        return None
    if value:
        return Path(value)
    return DEFAULT_MODEL if DEFAULT_MODEL.exists() else None


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    # Polillas nuevas por trampa por semana a partir de las cuales se alerta.
    # Placeholder: el umbral real lo define ISCAMEN según zona y momento.
    weekly_alert_threshold: int = 10
    max_upload_mb: int = 15
    # None = conteo clásico. Con modelo, requiere el extra [yolo].
    model_path: Path | None = None
    model_conf: float = 0.4
    model_imgsz: int = 960

    @property
    def db_path(self) -> Path:
        return self.data_dir / "vitisguard.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=Path(os.environ.get("VG_DATA_DIR", "./data")),
            weekly_alert_threshold=int(os.environ.get("VG_WEEKLY_ALERT", "10")),
            max_upload_mb=int(os.environ.get("VG_MAX_UPLOAD_MB", "15")),
            model_path=_model_from_env(),
            model_conf=float(os.environ.get("VG_MODEL_CONF", "0.4")),
            model_imgsz=int(os.environ.get("VG_MODEL_IMGSZ", "960")),
        )

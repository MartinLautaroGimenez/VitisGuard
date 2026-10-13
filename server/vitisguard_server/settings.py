from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    # Polillas nuevas por trampa por semana a partir de las cuales se alerta.
    # Placeholder: el umbral real lo define ISCAMEN según zona y momento.
    weekly_alert_threshold: int = 10
    max_upload_mb: int = 15

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
        )

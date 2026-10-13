"""Cola persistente en disco: las fotos se guardan antes de intentar subirlas.

Cada captura son dos archivos con el mismo nombre: <stamp>.jpg y
<stamp>.json. El .json se escribe último (vía rename atómico), así que una
captura existe para la cola solo cuando está completa.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Item:
    image: Path
    metadata_path: Path

    @property
    def metadata(self) -> dict:
        return json.loads(self.metadata_path.read_text())

    def remove(self) -> None:
        self.metadata_path.unlink(missing_ok=True)
        self.image.unlink(missing_ok=True)


class Outbox:
    def __init__(self, directory: Path, max_items: int = 60):
        self.dir = directory
        self.max_items = max_items
        self.dir.mkdir(parents=True, exist_ok=True)

    def put(self, stamp: str, image: Path, metadata: dict) -> Item:
        dest = self.dir / f"{stamp}.jpg"
        shutil.move(str(image), dest)
        tmp = self.dir / f".{stamp}.json.tmp"
        tmp.write_text(json.dumps(metadata))
        os.replace(tmp, self.dir / f"{stamp}.json")
        self._trim()
        return Item(dest, self.dir / f"{stamp}.json")

    def pending(self) -> list[Item]:
        items = []
        for meta in sorted(self.dir.glob("*.json")):
            img = meta.with_suffix(".jpg")
            if img.exists():
                items.append(Item(img, meta))
            else:
                meta.unlink()
        return items

    def _trim(self) -> None:
        items = self.pending()
        for item in items[: max(0, len(items) - self.max_items)]:
            log.warning("cola llena, se descarta la captura más vieja: %s", item.image.name)
            item.remove()

    def flush(self, send: Callable[[Item], bool]) -> int:
        """Sube en orden cronológico; corta en el primer fallo (sin red, etc.)."""
        sent = 0
        for item in self.pending():
            if not send(item):
                break
            item.remove()
            sent += 1
        return sent

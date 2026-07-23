"""Entrenamiento del detector YOLO11 para Lobesia botrana.

Requisitos:  pip install -r requirements-yolo.txt   (agrega ultralytics + torch)
Recomendado: Python 3.11/3.12 (torch suele no tener wheels para 3.14 todavía).

Dataset (formato YOLO):
  Conseguí/etiquetá un dataset de trampas con polillas. Un buen punto de partida son
  los datasets públicos de "grape moth" / "Lobesia botrana" en Roboflow, exportados a
  formato YOLOv8. Debe incluir un data.yaml con: path, train, val y names (clases).

Uso:
    python train.py --data /ruta/al/dataset/data.yaml --epochs 100 --imgsz 640
El mejor modelo se copia a models/lobesia.pt para que el microservicio lo use
automáticamente (backend YOLO).
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent / "models"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True, help="ruta al data.yaml del dataset")
    p.add_argument("--base", default="yolo11n.pt", help="modelo base (nano por defecto)")
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", default="", help="'cpu', '0', etc. (vacío = auto)")
    args = p.parse_args()

    from ultralytics import YOLO  # import perezoso (dependencia pesada)

    model = YOLO(args.base)
    results = model.train(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz,
        batch=args.batch, device=args.device or None,
        project=str(Path(__file__).resolve().parent / "runs"),
        name="lobesia",
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dest = MODELS_DIR / "lobesia.pt"
    if best.exists():
        shutil.copy(best, dest)
        print(f"\n✔ Modelo entrenado copiado a {dest}")
        print("Reiniciá el microservicio: usará automáticamente el backend YOLO.")
    else:
        print("No se encontró best.pt; revisá el entrenamiento.")


if __name__ == "__main__":
    main()

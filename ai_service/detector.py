"""Detección/conteo de polillas en la imagen de la trampa.

Dos backends, seleccionados automáticamente:
  * ``yolo``: Ultralytics YOLO11 si hay pesos entrenados (models/*.pt o AI_MODEL_PATH)
    y ultralytics está instalado. Es el camino de producción (entrenable con train.py).
  * ``cv``:   detector clásico por visión (OpenCV) que cuenta blobs oscuros sobre el
    engomado. Funciona sin modelo entrenado -> la IA da resultados desde el minuto cero.

La respuesta es homogénea para ambos backends.
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("vitisguard.detector")

MODELS_DIR = Path(__file__).resolve().parent / "models"
SPECIES_DEFAULT = "Lobesia botrana"


class Detector:
    def __init__(self) -> None:
        self.backend = "cv"
        self._yolo = None
        self._load()

    def _load(self) -> None:
        weights = self._find_weights()
        if weights and os.environ.get("AI_USE_YOLO", "auto") != "off":
            try:
                from ultralytics import YOLO
                self._yolo = YOLO(str(weights))
                self.backend = "yolo"
                log.info("Detector: backend YOLO (%s)", weights.name)
                return
            except Exception as exc:  # noqa: BLE001
                log.warning("No se pudo cargar YOLO (%s); uso backend CV.", exc)
        log.info("Detector: backend CV (clásico). Entrená un modelo con train.py para YOLO.")

    @staticmethod
    def _find_weights() -> Path | None:
        env = os.environ.get("AI_MODEL_PATH")
        if env and Path(env).exists():
            return Path(env)
        if MODELS_DIR.exists():
            for pt in sorted(MODELS_DIR.glob("*.pt")):
                return pt
        return None

    # ------------------------------------------------------------------ #
    def detect(self, image_bytes: bytes) -> dict:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {"count": 0, "species": None, "confidence": None,
                    "detections": [], "annotated_png_b64": None, "backend": self.backend}
        if self.backend == "yolo":
            return self._detect_yolo(img)
        return self._detect_cv(img)

    # ------------------------------------------------------------------ #
    def _detect_yolo(self, img) -> dict:
        h, w = img.shape[:2]
        results = self._yolo.predict(img, verbose=False,
                                     conf=float(os.environ.get("AI_CONF", "0.25")))[0]
        detections, confs = [], []
        names = results.names
        for box in results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = names.get(int(box.cls[0]), SPECIES_DEFAULT) if isinstance(names, dict) else SPECIES_DEFAULT
            confs.append(conf)
            detections.append({
                "x": x1 / w, "y": y1 / h, "w": (x2 - x1) / w, "h": (y2 - y1) / h,
                "class_name": cls, "confidence": round(conf, 3),
            })
        annotated = results.plot()  # BGR con cajas
        return self._pack(detections, confs, annotated)

    def _detect_cv(self, img) -> dict:
        """Cuenta blobs oscuros (polillas) sobre el engomado amarillo."""
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        # Umbral de Otsu inverso: separa lo oscuro (polilla) del engomado claro.
        _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = np.ones((3, 3), np.uint8)
        thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel, iterations=1)
        # RETR_LIST (no EXTERNAL): el borde de la trampa encierra a las polillas;
        # con EXTERNAL sólo se vería el borde. El borde se descarta luego por tamaño.
        contours, _ = cv2.findContours(thr, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        img_area = h * w
        detections, confs = [], []
        annotated = img.copy()
        for c in contours:
            x, y, bw, bh = cv2.boundingRect(c)
            area = bw * bh
            # filtrar ruido, el borde de la trampa y manchas demasiado grandes
            if area < img_area * 0.00025 or area > img_area * 0.04:
                continue
            aspect = bw / max(bh, 1)
            if aspect > 6 or aspect < 0.15:
                continue
            conf = round(min(0.95, 0.6 + area / (img_area * 0.04) * 0.35), 3)
            confs.append(conf)
            detections.append({
                "x": x / w, "y": y / h, "w": bw / w, "h": bh / h,
                "class_name": SPECIES_DEFAULT, "confidence": conf,
            })
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), (0, 0, 255), 2)
        return self._pack(detections, confs, annotated)

    # ------------------------------------------------------------------ #
    def _pack(self, detections, confs, annotated_bgr) -> dict:
        count = len(detections)
        ok, buf = cv2.imencode(".png", annotated_bgr)
        annotated_b64 = base64.b64encode(buf.tobytes()).decode() if ok else None
        return {
            "count": count,
            "species": SPECIES_DEFAULT if count else None,
            "confidence": round(float(np.mean(confs)), 3) if confs else None,
            "detections": detections,
            "annotated_png_b64": annotated_b64,
            "backend": self.backend,
        }


_detector: Detector | None = None


def get_detector() -> Detector:
    global _detector
    if _detector is None:
        _detector = Detector()
    return _detector

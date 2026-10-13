"""Conteo de polillas sobre el piso engomado de una trampa delta.

El piso es blanco con una grilla impresa y las polillas son manchas
oscuras de ~8 x 3 mm. El enfoque es clásico (sin red neuronal) para que
funcione desde el día uno sin dataset etiquetado:

1. Normalizar la iluminación dividiendo por un fondo estimado.
2. Umbralizar lo oscuro.
3. Una apertura morfológica borra las líneas finas de la grilla.
4. Filtrar contornos por área; los grupos de polillas pegadas se
   estiman por área relativa a la mediana de una polilla individual.

Todos los tamaños se expresan como fracción del ancho de la imagen para
no depender de la resolución de la cámara.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass(frozen=True)
class DetectionParams:
    # Umbral sobre la imagen normalizada (255 = fondo). Menor = más estricto.
    threshold: int = 150
    # Tamaño del kernel de apertura; debe superar el grosor de la grilla
    # y ser menor que el ancho de una polilla.
    open_frac: float = 0.006
    # Área mínima de un blob (fracción del área de la imagen).
    min_area_frac: float = 1.0e-4
    # Un blob mayor a este múltiplo de la mediana se trata como grupo.
    cluster_factor: float = 1.6


@dataclass
class Detection:
    x: int
    y: int
    w: int
    h: int
    area: float
    count: int


@dataclass
class DetectionResult:
    count: int
    detections: list[Detection] = field(default_factory=list)


def _odd(n: float) -> int:
    n = max(3, int(round(n)))
    return n if n % 2 else n + 1


def count_moths(image: np.ndarray, params: DetectionParams = DetectionParams()) -> DetectionResult:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    h, w = gray.shape

    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    background = cv2.medianBlur(gray, _odd(w / 12))
    norm = cv2.divide(gray, np.maximum(background, 1), scale=255)

    _, mask = cv2.threshold(norm, params.threshold, 255, cv2.THRESH_BINARY_INV)
    k = _odd(w * params.open_frac)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = params.min_area_frac * h * w
    blobs = [(c, cv2.contourArea(c)) for c in contours]
    blobs = [(c, a) for c, a in blobs if a >= min_area]
    if not blobs:
        return DetectionResult(count=0)

    # La mediana representa una polilla aislada mientras la mayoría de los
    # blobs sean individuales, que es lo normal en una trampa.
    single = float(np.median([a for _, a in blobs]))
    detections = []
    for c, a in blobs:
        n = 1
        if a > params.cluster_factor * single:
            n = max(1, int(round(a / single)))
        x, y, bw, bh = cv2.boundingRect(c)
        detections.append(Detection(x, y, bw, bh, a, n))
    return DetectionResult(count=sum(d.count for d in detections), detections=detections)


def annotate(image: np.ndarray, result: DetectionResult) -> np.ndarray:
    out = image.copy() if image.ndim == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    thickness = max(2, out.shape[1] // 600)
    for d in result.detections:
        color = (0, 0, 255) if d.count == 1 else (0, 140, 255)
        cv2.rectangle(out, (d.x, d.y), (d.x + d.w, d.y + d.h), color, thickness)
        if d.count > 1:
            cv2.putText(out, str(d.count), (d.x, d.y - 4), cv2.FONT_HERSHEY_SIMPLEX,
                        thickness * 0.5, color, thickness)
    cv2.putText(out, f"Total: {result.count}", (20, 20 + 30 * thickness),
                cv2.FONT_HERSHEY_SIMPLEX, thickness, (0, 0, 255), thickness * 2)
    return out

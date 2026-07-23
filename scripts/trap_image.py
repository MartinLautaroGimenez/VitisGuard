"""Generador de imágenes sintéticas de trampa delta.

Usado por el seed y el simulador para producir capturas realistas SIN hardware:
dibuja un fondo de trampa engomada (amarillo) con N "polillas" (blobs oscuros).
"""
from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw, ImageFilter


def generate_trap_image(num_moths: int = 0, width: int = 480, height: int = 480,
                        seed: int | None = None) -> bytes:
    rnd = random.Random(seed)
    img = Image.new("RGB", (width, height), (222, 205, 120))  # engomado amarillo
    draw = ImageDraw.Draw(img)

    # textura / suciedad de fondo
    for _ in range(600):
        x, y = rnd.randint(0, width), rnd.randint(0, height)
        shade = rnd.randint(180, 215)
        draw.point((x, y), fill=(shade, shade - 15, 90))

    # borde de la trampa
    draw.rectangle([6, 6, width - 6, height - 6], outline=(120, 100, 40), width=3)

    # polillas (cuerpo oscuro elongado + alas grisáceas, claramente contrastadas)
    for _ in range(max(0, num_moths)):
        cx, cy = rnd.randint(35, width - 35), rnd.randint(35, height - 35)
        length = rnd.randint(14, 22)
        wing = rnd.randint(9, 14)
        body = (rnd.randint(45, 70),) * 3      # cuerpo oscuro
        wings = (rnd.randint(80, 105),) * 3    # alas algo más claras
        # alas (dos elipses a los lados)
        draw.ellipse([cx - wing, cy - wing // 2, cx + 2, cy + wing // 2], fill=wings)
        draw.ellipse([cx - 2, cy - wing // 2, cx + wing, cy + wing // 2], fill=wings)
        # cuerpo central
        draw.ellipse([cx - 3, cy - length // 2, cx + 3, cy + length // 2], fill=body)

    img = img.filter(ImageFilter.GaussianBlur(0.5))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return buf.getvalue()

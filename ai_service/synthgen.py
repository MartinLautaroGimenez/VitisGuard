"""Generador de dataset sintético auto-etiquetado (formato YOLO) para Lobesia botrana.

La clave: cada "polilla" se dibuja como un sprite con posición, tamaño y rotación
conocidos, así que la caja (bounding box) sale exacta -> etiquetado automático, cero
trabajo manual. El resultado entrena un detector YOLO real (mucho mejor que contar
blobs con OpenCV) y es 100% reproducible en la GTX 1050.

Genera:
    <out>/images/train/*.jpg   <out>/labels/train/*.txt
    <out>/images/val/*.jpg     <out>/labels/val/*.txt
    <out>/data.yaml

Uso:
    python synthgen.py --out datasets/lobesia_synth --train 1000 --val 200
Cada .txt YOLO: una línea por polilla -> "0 cx cy w h" (normalizado 0..1, clase 0).
"""
from __future__ import annotations

import argparse
import io
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CLASS_NAME = "Lobesia botrana"


# --------------------------------------------------------------------------- #
# Sprite de una polilla (cuerpo oscuro elongado + alas mota grisáceo-marrón)
# --------------------------------------------------------------------------- #
def _moth_sprite(rng: random.Random, body_len: int) -> Image.Image:
    span = int(body_len * rng.uniform(0.75, 1.15))          # envergadura
    pad = 5
    cw, ch = span + 2 * pad, body_len + 2 * pad
    sprite = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(sprite)
    cx, cy = cw // 2, ch // 2

    # tono marrón grisáceo con jitter (las Lobesia se ven marroncitas sobre el engomado)
    b = rng.randint(70, 120)
    wing = (b + rng.randint(-12, 12), b + rng.randint(-18, 6), b + rng.randint(-30, -6))
    wing = tuple(max(35, min(160, c)) for c in wing)
    body = tuple(max(25, c - 42) for c in wing)

    # alas: dos elipses a los lados
    d.ellipse([cx - span // 2, cy - body_len // 3, cx + 2, cy + body_len // 3],
              fill=wing + (255,))
    d.ellipse([cx - 2, cy - body_len // 3, cx + span // 2, cy + body_len // 3],
              fill=wing + (255,))
    # cuerpo central
    bw = max(2, span // 9)
    d.ellipse([cx - bw, cy - body_len // 2, cx + bw, cy + body_len // 2],
              fill=body + (255,))
    # moteado en las alas (fibra/escamas)
    for _ in range(rng.randint(4, 10)):
        fx = rng.randint(cx - span // 2, cx + span // 2)
        fy = rng.randint(cy - body_len // 3, cy + body_len // 3)
        d.point((fx, fy), fill=body + (255,))

    return sprite.rotate(rng.uniform(0, 360), expand=True, resample=Image.BICUBIC)


# --------------------------------------------------------------------------- #
# Fondo de trampa engomada amarilla con iluminación/suciedad variable
# --------------------------------------------------------------------------- #
def _background(size: tuple[int, int], rng: random.Random) -> Image.Image:
    W, H = size
    base = (rng.randint(214, 232), rng.randint(198, 212), rng.randint(105, 130))
    arr = np.full((H, W, 3), base, dtype=np.float32)

    # gradiente de iluminación lineal aleatorio (0.82..1.18)
    gx, gy = rng.uniform(-1, 1), rng.uniform(-1, 1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    grad = xx / W * gx + yy / H * gy
    grad = (grad - grad.min()) / (np.ptp(grad) + 1e-6)
    arr *= (0.82 + 0.36 * grad)[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    d = ImageDraw.Draw(img)
    # suciedad/textura del engomado
    for _ in range(rng.randint(250, 800)):
        x, y = rng.randint(0, W - 1), rng.randint(0, H - 1)
        s = rng.randint(185, 215)
        d.point((x, y), fill=(s, s - 15, 90))
    # distractores NO-polilla (rayas/manchas claras) -> el modelo aprende a ignorarlos
    for _ in range(rng.randint(0, 6)):
        x0, y0 = rng.randint(0, W), rng.randint(0, H)
        d.line([x0, y0, x0 + rng.randint(-35, 35), y0 + rng.randint(-35, 35)],
               fill=(rng.randint(195, 215), rng.randint(180, 200), rng.randint(100, 120)),
               width=1)
    # borde de la trampa
    d.rectangle([5, 5, W - 5, H - 5], outline=(120, 100, 40), width=3)
    return img


def _render(rng: random.Random, size: int, max_moths: int):
    """Devuelve (PIL.Image, [ (cx,cy,w,h) normalizado, ... ])."""
    W = H = size
    img = _background((W, H), rng)

    # count con sesgo hacia pocos; ~12% de trampas vacías (negativos reales)
    if rng.random() < 0.12:
        n = 0
    else:
        n = 1 + int(abs(rng.gauss(0, 1)) * max_moths / 3)
        n = max(1, min(max_moths, n))

    boxes = []
    for _ in range(n):
        body_len = rng.randint(int(size * 0.025), int(size * 0.06))  # ~16..38 px @640
        sprite = _moth_sprite(rng, body_len)
        sw, sh = sprite.size
        px = rng.randint(10, max(11, W - sw - 10))
        py = rng.randint(10, max(11, H - sh - 10))
        img.paste(sprite, (px, py), sprite)

        bb = sprite.getbbox()  # caja ajustada del contenido (alpha) dentro del sprite
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        ax0, ay0, ax1, ay1 = px + x0, py + y0, px + x1, py + y1
        cx = (ax0 + ax1) / 2 / W
        cy = (ay0 + ay1) / 2 / H
        bw = (ax1 - ax0) / W
        bh = (ay1 - ay0) / H
        boxes.append((cx, cy, bw, bh))

    # desenfoque leve + compresión JPEG variable (realismo de cámara)
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.9)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=rng.randint(70, 92))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), boxes


# --------------------------------------------------------------------------- #
def _emit(split: str, n: int, out: Path, rng: random.Random, size_range, max_moths):
    img_dir = out / "images" / split
    lbl_dir = out / "labels" / split
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)
    total_moths = 0
    for i in range(n):
        size = rng.choice(size_range)
        img, boxes = _render(rng, size, max_moths)
        stem = f"{split}_{i:05d}"
        img.save(img_dir / f"{stem}.jpg", quality=90)
        lines = [f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}" for cx, cy, w, h in boxes]
        (lbl_dir / f"{stem}.txt").write_text("\n".join(lines))
        total_moths += len(boxes)
    print(f"  {split}: {n} imágenes, {total_moths} polillas etiquetadas")


def generate(out: Path, n_train: int, n_val: int, max_moths: int, seed: int) -> Path:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    size_range = [512, 576, 640, 704]
    print(f"Generando dataset sintético en {out} ...")
    _emit("train", n_train, out, rng, size_range, max_moths)
    _emit("val", n_val, out, rng, size_range, max_moths)

    data_yaml = out / "data.yaml"
    data_yaml.write_text(
        f"path: {out.resolve()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n  0: {CLASS_NAME}\n"
    )
    print(f"data.yaml -> {data_yaml}")
    return data_yaml


def main() -> None:
    p = argparse.ArgumentParser(description="Generador de dataset sintético YOLO (Lobesia)")
    p.add_argument("--out", default="datasets/lobesia_synth", help="carpeta de salida")
    p.add_argument("--train", type=int, default=1000)
    p.add_argument("--val", type=int, default=200)
    p.add_argument("--max-moths", type=int, default=24)
    p.add_argument("--seed", type=int, default=2026)
    args = p.parse_args()
    generate(Path(args.out), args.train, args.val, args.max_moths, args.seed)


if __name__ == "__main__":
    main()

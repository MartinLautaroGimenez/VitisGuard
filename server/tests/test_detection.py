import cv2
import numpy as np
import pytest

from vitisguard_server.detection import annotate, count_moths

W, H = 1600, 1200


def sticky_floor(seed=0):
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), 225, np.uint8)
    # Viñeteo: más oscuro en los bordes, como con el LED en el techo de la trampa.
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.hypot((xx - W / 2) / W, (yy - H / 2) / H)
    img = (img * (1 - 0.35 * r)[..., None]).astype(np.uint8)
    for x in range(0, W, 100):
        cv2.line(img, (x, 0), (x, H), (150, 150, 150), 3)
    for y in range(0, H, 100):
        cv2.line(img, (0, y), (W, y), (150, 150, 150), 3)
    noise = rng.normal(0, 4, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8), rng


def moth(img, center, angle):
    cv2.ellipse(img, center, (32, 12), angle, 0, 360, (45, 55, 70), -1)


@pytest.mark.parametrize("n", [0, 1, 7, 25])
def test_counts_isolated_moths(n):
    img, rng = sticky_floor(n)
    placed = []
    while len(placed) < n:
        c = (int(rng.integers(60, W - 60)), int(rng.integers(60, H - 60)))
        if all(np.hypot(c[0] - p[0], c[1] - p[1]) > 90 for p in placed):
            placed.append(c)
            moth(img, c, int(rng.integers(0, 180)))
    assert count_moths(img).count == n


def test_overlapping_moths_counted_as_group():
    img, _ = sticky_floor()
    for c in [(200, 200), (600, 300), (900, 900), (1300, 500)]:
        moth(img, c, 30)
    moth(img, (1000, 400), 0)
    moth(img, (1050, 405), 10)  # pegada a la anterior
    assert count_moths(img).count == 6


def test_annotate_keeps_shape():
    img, _ = sticky_floor()
    moth(img, (400, 400), 0)
    out = annotate(img, count_moths(img))
    assert out.shape == img.shape


def test_yolo_counter_with_bundled_model():
    pytest.importorskip("ultralytics")
    from vitisguard_server.detection import load_counter
    from vitisguard_server.settings import DEFAULT_MODEL

    counter = load_counter(DEFAULT_MODEL)
    assert counter.name.startswith("yolo:")
    img, _ = sticky_floor()
    moth(img, (400, 400), 0)
    # Manchas sintéticas no son polillas reales: el modelo no debería contarlas.
    assert counter(img).count == 0


def test_load_counter_without_model_is_classic():
    from vitisguard_server.detection import load_counter

    assert load_counter(None).name == "classic"

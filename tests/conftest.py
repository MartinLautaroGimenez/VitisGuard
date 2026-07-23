import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import Node  # noqa: E402


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def node(app):
    n = Node(node_id="VG-TEST", name="Nodo Test", api_token="test-token-123",
             latitude=-33.0, longitude=-68.8)
    db.session.add(n)
    db.session.commit()
    return n


@pytest.fixture()
def jpeg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (222, 205, 120)).save(buf, format="JPEG")
    return buf.getvalue()

"""Entrypoint de VitisGuard.

Uso:
    python run.py                 # HTTP en localhost:5000
    python run.py --https         # HTTPS con certificado adhoc (dev)

Variables de entorno relevantes en .env (ver .env.example).
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

load_dotenv()  # carga .env antes de leer la config

from app import create_app  # noqa: E402

app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="VitisGuard server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--https", action="store_true", help="TLS adhoc (solo dev)")
    args = parser.parse_args()

    ssl_context = "adhoc" if args.https else None
    app.run(host=args.host, port=args.port, ssl_context=ssl_context, debug=app.debug)


if __name__ == "__main__":
    main()

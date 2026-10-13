"""Administración: python -m vitisguard_server.cli add-trap trampa-001 --name "Finca ..." """

from __future__ import annotations

import argparse

from . import db
from .settings import Settings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="vitisguard-admin")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add-trap", help="registrar una trampa y generar su token")
    add.add_argument("trap_id")
    add.add_argument("--name", required=True)
    add.add_argument("--lat", type=float)
    add.add_argument("--lon", type=float)

    sub.add_parser("list-traps")

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = db.connect(settings.db_path)

    if args.cmd == "add-trap":
        token = db.add_trap(conn, args.trap_id, args.name, args.lat, args.lon)
        print(f"Trampa {args.trap_id} registrada.")
        print(f"Token (copialo al config.yaml del equipo, no se vuelve a mostrar):\n{token}")
    elif args.cmd == "list-traps":
        for row in conn.execute("SELECT id, name, lat, lon, created_at FROM traps ORDER BY id"):
            print(dict(row))


if __name__ == "__main__":
    main()

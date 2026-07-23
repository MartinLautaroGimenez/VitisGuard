"""Rutas del dashboard web (páginas Jinja) y exportación de reportes."""
from __future__ import annotations

import csv
import io
from datetime import timedelta

from flask import Blueprint, Response, render_template, request

from ..models import Capture, Node, Reading, utcnow

dashboard_bp = Blueprint("dashboard", __name__)


def _nodes():
    return Node.query.order_by(Node.node_id).all()


@dashboard_bp.get("/")
def overview():
    return render_template("dashboard.html", nodes=_nodes())


@dashboard_bp.get("/nodes")
def nodes_page():
    return render_template("nodes.html", nodes=_nodes())


@dashboard_bp.get("/nodes/<node_id>")
def node_detail_page(node_id):
    node = Node.query.filter_by(node_id=node_id).first_or_404()
    return render_template("node_detail.html", node=node)


@dashboard_bp.get("/charts")
def charts_page():
    return render_template("charts.html", nodes=_nodes())


@dashboard_bp.get("/gallery")
def gallery_page():
    species = [s[0] for s in (Capture.query.with_entities(Capture.species)
                              .filter(Capture.species.isnot(None)).distinct().all())]
    return render_template("gallery.html", nodes=_nodes(), species=species)


@dashboard_bp.get("/alerts")
def alerts_page():
    return render_template("alerts.html", nodes=_nodes())


@dashboard_bp.get("/reports")
def reports_page():
    return render_template("reports.html", nodes=_nodes())


@dashboard_bp.get("/reports/export.csv")
def export_csv():
    kind = request.args.get("type", "readings")
    node_key = request.args.get("node")
    try:
        days = max(1, min(365, int(request.args.get("days", 30))))
    except (ValueError, TypeError):
        days = 30
    since = utcnow() - timedelta(days=days)

    node = Node.query.filter_by(node_id=node_key).first() if node_key else None
    buf = io.StringIO()
    writer = csv.writer(buf)

    if kind == "captures":
        writer.writerow(["node_id", "timestamp", "detection_count", "species",
                         "confidence", "status"])
        q = Capture.query.filter(Capture.timestamp >= since)
        if node:
            q = q.filter(Capture.node_id == node.id)
        for c in q.order_by(Capture.timestamp).all():
            writer.writerow([c.node.node_id, c.timestamp, c.detection_count,
                             c.species or "", c.confidence or "", c.status])
        filename = "vitisguard_capturas.csv"
    else:
        writer.writerow(["node_id", "timestamp", "temperature", "humidity",
                         "battery_v", "source"])
        q = Reading.query.filter(Reading.timestamp >= since)
        if node:
            q = q.filter(Reading.node_id == node.id)
        for r in q.order_by(Reading.timestamp).all():
            writer.writerow([r.node.node_id, r.timestamp, r.temperature,
                             r.humidity, r.battery_v or "", r.source])
        filename = "vitisguard_lecturas.csv"

    return Response(
        buf.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

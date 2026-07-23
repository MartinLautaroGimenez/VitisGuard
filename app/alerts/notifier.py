"""Notificadores de alertas.

Backend por defecto: ``log`` (la alerta se registra y se ve en el dashboard).
Los backends ``email`` (SMTP) y ``whatsapp`` (Twilio) están implementados como
stubs listos para activar completando credenciales en .env y NOTIFIER_BACKEND.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger("vitisguard.alerts")


class Notifier:
    def send(self, alert) -> None:  # pragma: no cover - interfaz
        raise NotImplementedError


class LogNotifier(Notifier):
    """Registra la alerta. Siempre activo; el dashboard la muestra igualmente."""

    def send(self, alert) -> None:
        log.warning("ALERTA [%s/%s] nodo=%s :: %s (valor=%s)",
                    alert.type, alert.level,
                    alert.node.node_id if alert.node else "?",
                    alert.message, alert.value)


class EmailNotifier(Notifier):
    """Envío por SMTP. Requiere SMTP_HOST/USER/PASSWORD y ALERT_EMAIL_TO."""

    def send(self, alert) -> None:
        cfg = current_app.config
        if not (cfg.get("SMTP_HOST") and cfg.get("ALERT_EMAIL_TO")):
            log.error("EmailNotifier sin configurar (SMTP_HOST/ALERT_EMAIL_TO); se omite envío.")
            return
        msg = EmailMessage()
        msg["Subject"] = f"[VitisGuard] Alerta {alert.level} en {alert.node.node_id}"
        msg["From"] = cfg.get("SMTP_USER")
        msg["To"] = cfg["ALERT_EMAIL_TO"]
        msg.set_content(
            f"Nodo: {alert.node.node_id} ({alert.node.name})\n"
            f"Tipo: {alert.type}\nNivel: {alert.level}\n"
            f"Mensaje: {alert.message}\nValor: {alert.value}\n"
            f"Fecha: {alert.timestamp}"
        )
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"]) as s:
            s.starttls()
            if cfg.get("SMTP_USER"):
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            s.send_message(msg)
        log.info("Alerta enviada por email a %s", cfg["ALERT_EMAIL_TO"])


class WhatsAppNotifier(Notifier):
    """Envío por WhatsApp vía API de Twilio. Requiere TWILIO_* y ALERT_WHATSAPP_TO."""

    def send(self, alert) -> None:
        cfg = current_app.config
        sid, token = cfg.get("TWILIO_SID"), cfg.get("TWILIO_TOKEN")
        if not (sid and token and cfg.get("ALERT_WHATSAPP_TO")):
            log.error("WhatsAppNotifier sin configurar (TWILIO_*); se omite envío.")
            return
        # Llamada REST directa (evita dependencia del SDK de Twilio).
        import requests
        body = (f"🍇 VitisGuard — Alerta {alert.level}\n"
                f"Nodo {alert.node.node_id}: {alert.message}")
        requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": cfg["TWILIO_FROM"], "To": cfg["ALERT_WHATSAPP_TO"], "Body": body},
            auth=(sid, token), timeout=10,
        ).raise_for_status()
        log.info("Alerta enviada por WhatsApp a %s", cfg["ALERT_WHATSAPP_TO"])


_BACKENDS = {"log": LogNotifier, "email": EmailNotifier, "whatsapp": WhatsAppNotifier}


def get_notifier() -> Notifier:
    backend = current_app.config.get("NOTIFIER_BACKEND", "log")
    return _BACKENDS.get(backend, LogNotifier)()


def notify(alert) -> None:
    """Envía la alerta por el backend configurado (nunca rompe el pipeline)."""
    try:
        get_notifier().send(alert)
    except Exception as exc:  # noqa: BLE001 - la notificación no debe tumbar la ingesta
        log.error("Fallo al notificar la alerta %s: %s", alert.id, exc)

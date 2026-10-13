#!/usr/bin/env bash
# Instalación en Raspberry Pi OS Lite (Bookworm). Correr como root desde device/.
set -euo pipefail

apt-get update
apt-get install -y python3-venv python3-yaml python3-requests python3-serial \
    python3-gpiozero rpicam-apps modemmanager network-manager

# 1-Wire para el DS18B20 (GPIO4)
grep -q '^dtoverlay=w1-gpio' /boot/firmware/config.txt || echo 'dtoverlay=w1-gpio' >> /boot/firmware/config.txt

python3 -m venv --system-site-packages /opt/vitisguard/venv
/opt/vitisguard/venv/bin/pip install --no-deps .

install -d -m 700 /etc/vitisguard /var/lib/vitisguard
[ -f /etc/vitisguard/config.yaml ] || install -m 600 config.example.yaml /etc/vitisguard/config.yaml

timedatectl set-timezone America/Argentina/Mendoza
install -m 644 systemd/*.service systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now vitisguard-sample.timer vitisguard-run.timer

echo "Listo. Editá /etc/vitisguard/config.yaml y probá: /opt/vitisguard/venv/bin/python -m vitisguard_device -v run"

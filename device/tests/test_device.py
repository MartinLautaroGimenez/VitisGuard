import json
from pathlib import Path

import pytest

from vitisguard_device import main as m
from vitisguard_device.config import Config
from vitisguard_device.hardware import Climate, read_dht22, read_ds18b20
from vitisguard_device.modem import parse_csq
from vitisguard_device.outbox import Outbox


@pytest.mark.parametrize("resp,expected", [
    ("\r\n+CSQ: 18,99\r\n\r\nOK\r\n", 18),
    ("+CSQ: 99,99\r\nOK", None),
    ("ERROR", None),
])
def test_parse_csq(resp, expected):
    assert parse_csq(resp) == expected


def fake_w1(tmp_path, content):
    d = tmp_path / "28-0000abcd"
    d.mkdir()
    (d / "w1_slave").write_text(content)
    return tmp_path


def test_ds18b20_ok(tmp_path):
    base = fake_w1(tmp_path, "4b 01 4b 46 7f ff 05 10 e1 : crc=e1 YES\n4b 01 4b 46 7f ff 05 10 e1 t=20687\n")
    assert read_ds18b20(base) == pytest.approx(20.687)


def test_ds18b20_bad_crc_and_power_on_value(tmp_path):
    assert read_ds18b20(fake_w1(tmp_path, "xx : crc=00 NO\nxx t=20000\n")) is None
    other = tmp_path / "other"
    other.mkdir()
    assert read_ds18b20(fake_w1(other, "xx : crc=e1 YES\nxx t=85000\n")) is None


def fake_iio(tmp_path, temp, hum, name="dht11"):
    d = tmp_path / "iio:device0"
    d.mkdir()
    (d / "name").write_text(name + "\n")
    (d / "in_temp_input").write_text(temp)
    (d / "in_humidityrelative_input").write_text(hum)
    return tmp_path


def test_dht22_ok(tmp_path):
    c = read_dht22(fake_iio(tmp_path, "23400\n", "41700\n"), retries=1)
    assert c == Climate(23.4, 41.7)


def test_dht22_ignores_other_iio_devices_and_bad_reads(tmp_path):
    assert read_dht22(fake_iio(tmp_path, "23400", "41700", name="ads1015"), retries=1) is None
    other = tmp_path / "x"
    other.mkdir()
    assert read_dht22(fake_iio(other, "23400", "150000"), retries=2, wait_s=0) is None


def make_image(tmp_path, name="img.jpg"):
    p = tmp_path / name
    p.write_bytes(b"\xff\xd8fake")
    return p


def test_outbox_flush_stops_on_failure(tmp_path):
    box = Outbox(tmp_path / "out")
    for i in range(3):
        box.put(f"2026101{i}T100000Z", make_image(tmp_path), {"i": i})
    calls = []

    def send(item):
        calls.append(item.metadata["i"])
        return len(calls) < 2

    assert box.flush(send) == 1
    assert calls == [0, 1]
    assert [it.metadata["i"] for it in box.pending()] == [1, 2]


def test_outbox_trims_oldest(tmp_path):
    box = Outbox(tmp_path / "out", max_items=2)
    for i in range(4):
        box.put(f"2026101{i}T100000Z", make_image(tmp_path), {"i": i})
    assert [it.metadata["i"] for it in box.pending()] == [2, 3]


def test_outbox_ignores_half_written_items(tmp_path):
    box = Outbox(tmp_path / "out")
    (box.dir / "20261010T100000Z.jpg").write_bytes(b"x")  # sin .json: incompleta
    assert box.pending() == []


@pytest.fixture
def cfg(tmp_path):
    return Config(trap_id="t1", token="tok", server_url="http://localhost:1", data_dir=tmp_path / "data")


def test_capture_bundles_temperatures_and_liner_flag(cfg, tmp_path, monkeypatch):
    monkeypatch.setattr(m.hardware, "capture_still", lambda path, w, h: Path(path).write_bytes(b"jpg"))
    monkeypatch.setattr(m.hardware, "read_climate", lambda sensor: Climate(21.5, 40.0))
    m.cmd_sample(cfg)
    m.cmd_sample(cfg)
    cfg.liner_flag.touch()

    item = m.cmd_capture(cfg, Outbox(cfg.outbox_dir))

    meta = item.metadata
    assert [(s["c"], s["h"]) for s in meta["temperatures"]] == [(21.5, 40.0)] * 2
    assert meta["liner_changed"] is True
    assert meta["taken_at"].endswith("+00:00")
    assert not cfg.temperature_log.exists() and not cfg.liner_flag.exists()


def test_config_load(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("trap_id: a\ntoken: b\nserver_url: http://x\ndata_dir: /tmp/vg\n"
                 "camera: {led_gpio: null}\nmodem: {power_gpio: 5}\n")
    c = Config.load(p)
    assert c.camera.led_gpio is None and c.camera.width == 2592
    assert c.modem.power_gpio == 5 and c.data_dir == Path("/tmp/vg")

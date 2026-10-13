from datetime import date, datetime, timedelta, timezone

import pytest

from vitisguard_server.phenology import (
    GenerationModel,
    daily_degree_days,
    dd_from_samples,
    dd_min_max,
    season_start,
)


def test_season_start():
    assert season_start(date(2026, 10, 13)) == date(2026, 7, 1)
    assert season_start(date(2027, 2, 1)) == date(2026, 7, 1)


def test_min_max_method():
    assert dd_min_max(5, 15) == 0
    assert dd_min_max(12, 28) == 10
    assert dd_min_max(20, 40) == 15  # corte superior en 30


def test_integration_beats_min_max_on_cold_nights():
    # 12 h a 6 °C y 12 h a 24 °C: el promedio da 5, pero solo la mitad del día suma.
    temps = [6.0] * 12 + [24.0] * 12
    assert dd_from_samples(temps) == pytest.approx(7.0)
    assert dd_min_max(6, 24) == pytest.approx(5.0)


def test_daily_grouping_uses_mendoza_local_day():
    # 02:00 UTC es todavía el día anterior en Mendoza (UTC-3).
    base = datetime(2026, 11, 2, 2, 0, tzinfo=timezone.utc)
    samples = [(base, 20.0), (base + timedelta(hours=4), 20.0)]
    days = daily_degree_days(samples)
    assert set(days) == {date(2026, 11, 1), date(2026, 11, 2)}


def test_generation_model():
    m = GenerationModel()
    assert m.current_flight(0) == 1
    assert m.current_flight(700) == 2
    assert m.current_flight(5000) == 4

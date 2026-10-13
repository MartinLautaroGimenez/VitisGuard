"""Grados-día para Lobesia botrana.

La polilla no se desarrolla por debajo de ~10 °C y el desarrollo deja de
acelerarse por encima de ~30 °C. Acumulando grados-día desde el inicio de
temporada se estima en qué vuelo/generación está la plaga y se anticipa
el momento de tratar (eclosión de huevos), que es lo que importa.

Los umbrales por generación son configurables: hay que calibrarlos con
los datos históricos de ISCAMEN para cada oasis (Norte, Este, Valle de
Uco, Sur), no tomarlos como verdad.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

MENDOZA = ZoneInfo("America/Argentina/Mendoza")
BASE_C = 10.0
UPPER_C = 30.0
# Con muestreo horario, un día con menos muestras usa el método min/máx.
MIN_SAMPLES_FOR_INTEGRATION = 18


def season_start(today: date) -> date:
    """La temporada arranca el 1 de julio (invierno austral, pupas en diapausa)."""
    year = today.year if today.month >= 7 else today.year - 1
    return date(year, 7, 1)


def dd_min_max(tmin: float, tmax: float, base: float = BASE_C, upper: float = UPPER_C) -> float:
    """Método del promedio con corte horizontal superior."""
    tmin, tmax = min(tmin, upper), min(tmax, upper)
    return max(0.0, (tmin + tmax) / 2 - base)


def dd_from_samples(temps: list[float], base: float = BASE_C, upper: float = UPPER_C) -> float:
    """Integra muestras equiespaciadas de un día; más preciso que min/máx."""
    if len(temps) >= MIN_SAMPLES_FOR_INTEGRATION:
        return sum(max(0.0, min(t, upper) - base) for t in temps) / len(temps)
    return dd_min_max(min(temps), max(temps), base, upper)


def daily_degree_days(samples: list[tuple[datetime, float]]) -> dict[date, float]:
    """Agrupa muestras (timestamp con zona, °C) por día local de Mendoza."""
    by_day: dict[date, list[float]] = defaultdict(list)
    for ts, celsius in samples:
        by_day[ts.astimezone(MENDOZA).date()].append(celsius)
    return {d: dd_from_samples(t) for d, t in sorted(by_day.items())}


@dataclass(frozen=True)
class GenerationModel:
    # Grados-día acumulados (base 10 °C desde el 1/7) al pico de cada vuelo.
    # Valores iniciales orientativos, A CALIBRAR con series de ISCAMEN.
    flight_peaks: tuple[float, ...] = (150.0, 700.0, 1250.0, 1800.0)

    def current_flight(self, accumulated: float) -> int:
        """Vuelo esperado (1..n) según los grados-día acumulados."""
        for i, peak in enumerate(self.flight_peaks):
            if i + 1 == len(self.flight_peaks):
                return i + 1
            if accumulated < (peak + self.flight_peaks[i + 1]) / 2:
                return i + 1
        return len(self.flight_peaks)

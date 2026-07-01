"""Matematyka geometrii tarczy: współrzędne kartezjańskie <-> polarne <-> sektor.

Układ współrzędnych tarczy (znormalizowany, w mm):
  * początek = środek bullseye,
  * oś X w prawo, oś Y w górę (układ matematyczny),
  * kąt mierzony ZGODNIE Z RUCHEM WSKAZÓWEK ZEGARA od góry (12:00).

Środek sektora 20 leży pod kątem 0° (po korekcie o `sector20_offset_deg`).
Wszystkie wymiary pochodzą z BoardConfig — brak stałych liczbowych w tym module.
"""

from __future__ import annotations

import math

from .config import BoardConfig


def cartesian_to_polar(x: float, y: float) -> tuple[float, float]:
    """(x, y) w mm -> (kąt_deg CW-od-góry w [0,360), promień w mm).

    Uwaga na konwencję kąta: atan2(x, y) daje kąt liczony od osi +Y (góra)
    zgodnie z ruchem wskazówek zegara:
        góra  (0,+1) -> 0°,  prawo (+1,0) -> 90°,
        dół   (0,-1) -> 180°, lewo (-1,0) -> 270°.
    """
    radius = math.hypot(x, y)
    angle = math.degrees(math.atan2(x, y)) % 360.0
    return angle, radius


def polar_to_cartesian(angle_deg: float, radius_mm: float) -> tuple[float, float]:
    """Odwrotność cartesian_to_polar (przydatne przy generowaniu syntetyków/testach)."""
    a = math.radians(angle_deg)
    return radius_mm * math.sin(a), radius_mm * math.cos(a)


def normalized_angle(angle_deg: float, board: BoardConfig) -> float:
    """Kąt po korekcie orientacji: 0° = środek sektora 20. Zwraca [0, 360)."""
    return (angle_deg - board.sector20_offset_deg) % 360.0


def sector_from_angle(angle_deg: float, board: BoardConfig) -> int:
    """Kąt (CW-od-góry, przed korektą) -> numer sektora 1..20.

    Sektor 20 zajmuje klin [-9°, +9°) wokół 0° po korekcie orientacji. Kolejne
    sektory co `sector_span_deg` zgodnie z `sector_order`. Granica jest półotwarta:
    dokładnie środek granicy trafia do sektora o wyższym indeksie (deterministyczny
    tie-break — istotne dla testów brzegowych).
    """
    a = normalized_angle(angle_deg, board)
    span = board.sector_span_deg
    # Przesuwamy o pół klina, żeby granice wypadały na wielokrotnościach span.
    idx = int((a + span / 2.0) // span) % len(board.sector_order)
    return board.sector_order[idx]


def sector_center_angle(sector: int, board: BoardConfig) -> float:
    """Kąt środka danego sektora (CW-od-góry, po uwzględnieniu offsetu)."""
    idx = board.sector_order.index(sector)
    return (idx * board.sector_span_deg + board.sector20_offset_deg) % 360.0


def angle_distance_to_boundary(angle_deg: float, board: BoardConfig) -> float:
    """Odległość kątowa (deg) do najbliższej granicy między sektorami."""
    a = normalized_angle(angle_deg, board)
    span = board.sector_span_deg
    # Granice leżą na (k*span + span/2). Reszta od najbliższej granicy:
    off = (a + span / 2.0) % span
    return min(off, span - off)

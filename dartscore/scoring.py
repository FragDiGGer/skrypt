"""Rdzeń punktacji: (kąt, promień) -> Hit.

To jest najbardziej krytyczny pod względem poprawności fragment modułu i jest
w pełni pokryty testami jednostkowymi (tests/test_scoring.py), łącznie z
przypadkami brzegowymi granic sektorów i pierścieni.

Konwencja przedziałów promienia jest PÓŁOTWARTA `[dolna, górna)`:
    bull         : [0, bull)
    outer_bull   : [bull, outer_bull)
    inner single : [outer_bull, triple_inner)
    triple       : [triple_inner, triple_outer)
    outer single : [triple_outer, double_inner)
    double       : [double_inner, double_outer)   <- double_outer WŁĄCZNIE do double
    miss         : [double_outer', ...)            <- powyżej double_outer

Uwaga: górna krawędź pola (double_outer) jest fizyczną krawędzią pola
punktowego, więc traktujemy dokładnie double_outer jako jeszcze trafienie
(double), a dopiero większy promień jako miss. To jedyny wyjątek od reguły
półotwartej i jest jawnie przetestowany.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from .config import BoardConfig
from .geometry import (
    cartesian_to_polar,
    sector_from_angle,
    angle_distance_to_boundary,
)

# Nazwy pierścieni zwracane w wyniku.
RING_BULL = "bull"
RING_OUTER_BULL = "outer_bull"
RING_SINGLE = "single"
RING_TRIPLE = "triple"
RING_DOUBLE = "double"
RING_MISS = "miss"

# Umowne "sektory" dla środka tarczy, zgodne z przykładami w specyfikacji:
#   outer bull -> sector 25, bull -> sector 50, miss -> sector null.
SECTOR_OUTER_BULL = 25
SECTOR_BULL = 50


@dataclass(frozen=True)
class Hit:
    """Wynik trafienia w ustrukturyzowanej formie.

    Pola zgodne z przykładami ze specyfikacji:
        {"sector": 20, "ring": "triple", "score": 60}
        {"sector": 25, "ring": "outer_bull", "score": 25}
        {"sector": 50, "ring": "bull", "score": 50}
        {"sector": null, "ring": "miss", "score": 0}
    """

    sector: Optional[int]
    ring: str
    multiplier: int
    score: int
    # Pola pomocnicze (diagnostyka / UI) — nie wymagane przez specyfikację.
    near_boundary: bool = False
    radius_mm: Optional[float] = None
    angle_deg: Optional[float] = None

    def to_dict(self) -> dict:
        """Pełny słownik (z polami diagnostycznymi)."""
        return asdict(self)

    def to_score_dict(self) -> dict:
        """Minimalny słownik zgodny z przykładami specyfikacji."""
        return {"sector": self.sector, "ring": self.ring, "score": self.score}


def _ring_and_multiplier(radius_mm: float, board: BoardConfig) -> tuple[str, int]:
    """Zmapuj promień na (nazwa_pierścienia, mnożnik) wg konwencji półotwartej."""
    r = board.rings
    if radius_mm < r.bull:
        return RING_BULL, 1
    if radius_mm < r.outer_bull:
        return RING_OUTER_BULL, 1
    if radius_mm < r.triple_inner:
        return RING_SINGLE, 1
    if radius_mm < r.triple_outer:
        return RING_TRIPLE, 3
    if radius_mm < r.double_inner:
        return RING_SINGLE, 1
    if radius_mm <= r.double_outer:  # krawędź pola włącznie -> nadal double
        return RING_DOUBLE, 2
    return RING_MISS, 0


def score(angle_deg: float, radius_mm: float, board: BoardConfig) -> Hit:
    """Zamień pozycję biegunową końcówki lotki na Hit.

    Args:
        angle_deg: kąt CW-od-góry (przed korektą orientacji; korekta w geometry).
        radius_mm: promień od środka bullseye w mm.
        board: geometria tarczy (BoardConfig) — jedyne źródło wymiarów.
    """
    if radius_mm < 0:
        raise ValueError("radius_mm nie może być ujemny")

    ring, multiplier = _ring_and_multiplier(radius_mm, board)

    if ring == RING_MISS:
        return Hit(
            sector=None, ring=RING_MISS, multiplier=0, score=0,
            near_boundary=False, radius_mm=radius_mm, angle_deg=angle_deg % 360.0,
        )

    if ring == RING_BULL:
        return Hit(
            sector=SECTOR_BULL, ring=RING_BULL, multiplier=1, score=50,
            near_boundary=False, radius_mm=radius_mm, angle_deg=angle_deg % 360.0,
        )

    if ring == RING_OUTER_BULL:
        return Hit(
            sector=SECTOR_OUTER_BULL, ring=RING_OUTER_BULL, multiplier=1, score=25,
            near_boundary=False, radius_mm=radius_mm, angle_deg=angle_deg % 360.0,
        )

    # Pola numeryczne 1..20 (single/triple/double).
    sector = sector_from_angle(angle_deg, board)
    near = (
        angle_distance_to_boundary(angle_deg, board) <= board.tolerances.boundary_angle_deg
        or _near_radius_boundary(radius_mm, board)
    )
    return Hit(
        sector=sector,
        ring=ring,
        multiplier=multiplier,
        score=sector * multiplier,
        near_boundary=near,
        radius_mm=radius_mm,
        angle_deg=angle_deg % 360.0,
    )


def score_cartesian(x_mm: float, y_mm: float, board: BoardConfig) -> Hit:
    """Wygodny wariant: pozycja kartezjańska (mm) -> Hit."""
    angle, radius = cartesian_to_polar(x_mm, y_mm)
    return score(angle, radius, board)


def _near_radius_boundary(radius_mm: float, board: BoardConfig) -> bool:
    """Czy promień jest blisko którejkolwiek granicy pierścienia (metryka niepewności)."""
    r = board.rings
    tol = board.tolerances.boundary_radius_mm
    for edge in (r.bull, r.outer_bull, r.triple_inner, r.triple_outer, r.double_inner, r.double_outer):
        if abs(radius_mm - edge) <= tol:
            return True
    return False

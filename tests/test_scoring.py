"""Wyczerpujące testy mapowania (kąt, promień) -> (sektor, mnożnik, punkty).

Priorytet poprawności: pokrywamy środki wszystkich sektorów oraz przypadki
brzegowe granic sektorów i pierścieni (konwencja półotwarta [dolna, górna),
z krawędzią double_outer włącznie do double).
"""

from __future__ import annotations

import math

import pytest

from dartscore.config import load_board_config
from dartscore.scoring import score, score_cartesian
from dartscore.geometry import sector_center_angle

BOARD = load_board_config()
SECTOR_ORDER = list(BOARD.sector_order)
# Środkowy promień pola single (bezpiecznie w inner single).
SINGLE_R = (BOARD.rings.outer_bull + BOARD.rings.triple_inner) / 2.0
TRIPLE_R = (BOARD.rings.triple_inner + BOARD.rings.triple_outer) / 2.0
DOUBLE_R = (BOARD.rings.double_inner + BOARD.rings.double_outer) / 2.0


def test_all_sector_centers_map_to_correct_number():
    """Środek każdego klina (co 18°) daje właściwy numer sektora."""
    for i, sector in enumerate(SECTOR_ORDER):
        angle = i * BOARD.sector_span_deg
        hit = score(angle, SINGLE_R, BOARD)
        assert hit.sector == sector, f"kąt {angle}° powinien dać sektor {sector}, dał {hit.sector}"
        assert hit.ring == "single"
        assert hit.score == sector


def test_sector_20_is_at_top():
    assert score(0.0, SINGLE_R, BOARD).sector == 20
    assert score(360.0, SINGLE_R, BOARD).sector == 20


def test_neighbors_of_20():
    """Sektor 1 na prawo od 20 (kąt +18°), sektor 5 na lewo (kąt -18° = 342°)."""
    assert score(18.0, SINGLE_R, BOARD).sector == 1
    assert score(342.0, SINGLE_R, BOARD).sector == 5


def test_triple_and_double_multipliers():
    t20 = score(0.0, TRIPLE_R, BOARD)
    assert (t20.sector, t20.ring, t20.multiplier, t20.score) == (20, "triple", 3, 60)
    d20 = score(0.0, DOUBLE_R, BOARD)
    assert (d20.sector, d20.ring, d20.multiplier, d20.score) == (20, "double", 2, 40)


@pytest.mark.parametrize("radius,expected_ring,expected_sector,expected_score", [
    (0.0, "bull", 50, 50),
    (BOARD.rings.bull - 0.01, "bull", 50, 50),
    (BOARD.rings.bull, "outer_bull", 25, 25),           # granica bull/25 -> 25 (półotwarte)
    (BOARD.rings.outer_bull - 0.01, "outer_bull", 25, 25),
    (BOARD.rings.outer_bull, "single", None, None),     # granica 25/single -> single
])
def test_bull_region_boundaries(radius, expected_ring, expected_sector, expected_score):
    hit = score(0.0, radius, BOARD)
    assert hit.ring == expected_ring
    if expected_ring in ("bull", "outer_bull"):
        assert hit.sector == expected_sector
        assert hit.score == expected_score


def test_triple_ring_boundaries():
    r = BOARD.rings
    assert score(0.0, r.triple_inner - 0.01, BOARD).ring == "single"
    assert score(0.0, r.triple_inner, BOARD).ring == "triple"          # dolna krawędź triple włącznie
    assert score(0.0, r.triple_outer - 0.01, BOARD).ring == "triple"
    assert score(0.0, r.triple_outer, BOARD).ring == "single"          # górna krawędź triple -> outer single


def test_double_and_miss_boundary():
    r = BOARD.rings
    assert score(0.0, r.double_inner - 0.01, BOARD).ring == "single"
    assert score(0.0, r.double_inner, BOARD).ring == "double"          # dolna krawędź double włącznie
    # Krawędź pola punktowego (double_outer) jest jeszcze trafieniem (double)...
    edge = score(0.0, r.double_outer, BOARD)
    assert edge.ring == "double" and edge.score == 40
    # ...a dopiero większy promień to miss.
    miss = score(0.0, r.double_outer + 0.01, BOARD)
    assert miss.ring == "miss"
    assert miss.sector is None
    assert miss.score == 0
    assert miss.multiplier == 0


def test_sector_boundary_tiebreak_is_deterministic():
    """Dokładna granica między 20 a 1 (kąt 9°) trafia deterministycznie do 1.

    Konwencja: granica leżąca na k*span + span/2 należy do sektora o wyższym
    indeksie (tu: 1). Test pilnuje, by tie-break był stabilny.
    """
    boundary = BOARD.sector_span_deg / 2.0  # 9°
    hit = score(boundary, SINGLE_R, BOARD)
    assert hit.sector == 1
    # Tuż poniżej granicy -> 20.
    assert score(boundary - 0.01, SINGLE_R, BOARD).sector == 20


def test_bull_independent_of_angle():
    """Bull i 25 nie zależą od kąta — sprawdzamy pełny obrót."""
    for deg in range(0, 360, 13):
        assert score(float(deg), 0.0, BOARD).ring == "bull"
        assert score(float(deg), (BOARD.rings.bull + BOARD.rings.outer_bull) / 2.0, BOARD).ring == "outer_bull"


def test_negative_radius_raises():
    with pytest.raises(ValueError):
        score(0.0, -1.0, BOARD)


def test_score_cartesian_matches_polar():
    """score_cartesian dla punktu na osi Y (góra) daje sektor 20."""
    hit = score_cartesian(0.0, TRIPLE_R, BOARD)
    assert hit.sector == 20 and hit.ring == "triple"


def test_offset_rotates_board():
    """Po ustawieniu offsetu sektora 20 na 18°, kąt 18° wskazuje na 20."""
    rotated = BOARD.with_offset(18.0)
    assert score(18.0, SINGLE_R, rotated).sector == 20
    assert score(0.0, SINGLE_R, rotated).sector == 5  # to co było lewym sąsiadem


def test_near_boundary_flag_set_close_to_edge():
    """Trafienie tuż przy granicy sektora ma near_boundary=True."""
    boundary = BOARD.sector_span_deg / 2.0
    assert score(boundary - 0.5, SINGLE_R, BOARD).near_boundary is True
    # Środek klina — z dala od granic promienia i kąta.
    assert score(0.0, SINGLE_R, BOARD).near_boundary is False

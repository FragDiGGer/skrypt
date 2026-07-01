"""Testy matematyki geometrii: konwencje kąta, konwersje, granice."""

from __future__ import annotations

import math

import pytest

from dartscore.config import load_board_config
from dartscore.geometry import (
    cartesian_to_polar,
    polar_to_cartesian,
    sector_from_angle,
    sector_center_angle,
    angle_distance_to_boundary,
)

BOARD = load_board_config()


@pytest.mark.parametrize("x,y,expected_angle", [
    (0.0, 1.0, 0.0),     # góra
    (1.0, 0.0, 90.0),    # prawo
    (0.0, -1.0, 180.0),  # dół
    (-1.0, 0.0, 270.0),  # lewo
])
def test_angle_convention_cw_from_top(x, y, expected_angle):
    angle, radius = cartesian_to_polar(x, y)
    assert radius == pytest.approx(1.0)
    assert angle == pytest.approx(expected_angle)


def test_polar_cartesian_roundtrip():
    for angle in (0.0, 37.0, 123.4, 250.0, 359.9):
        for radius in (5.0, 60.0, 165.0):
            x, y = polar_to_cartesian(angle, radius)
            a2, r2 = cartesian_to_polar(x, y)
            assert r2 == pytest.approx(radius)
            assert a2 == pytest.approx(angle, abs=1e-6)


def test_sector_from_angle_wraps():
    assert sector_from_angle(0.0, BOARD) == 20
    assert sector_from_angle(360.0, BOARD) == 20
    assert sector_from_angle(-18.0, BOARD) == 5  # równoważne 342°


def test_sector_center_angle_inverse():
    for sector in BOARD.sector_order:
        angle = sector_center_angle(sector, BOARD)
        assert sector_from_angle(angle, BOARD) == sector


def test_angle_distance_to_boundary():
    # Środek sektora (0°) jest maksymalnie oddalony od granic: pół klina = 9°.
    assert angle_distance_to_boundary(0.0, BOARD) == pytest.approx(9.0)
    # Na granicy (9°) odległość = 0.
    assert angle_distance_to_boundary(9.0, BOARD) == pytest.approx(0.0, abs=1e-9)

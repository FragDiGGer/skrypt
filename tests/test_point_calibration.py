"""Testy kalibracji perspektywicznej z 4 punktów (double 20/6/3/11).

Symulujemy realną perspektywę: budujemy prawdziwą homografię board→image
(trapez), rzutujemy nią punkty odniesienia i sprawdzamy, że kalibracja odtwarza
odwrotne odwzorowanie oraz że znany rzut jest poprawnie punktowany.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from dartscore.config import load_board_config
from dartscore.calibration.point_calibrator import (
    reference_board_point,
    calibrate_camera_from_points,
    build_calibration_from_points,
)
from dartscore.calibration.homography import image_to_board
from dartscore.scoring import score

BOARD = load_board_config()
R = BOARD.rings.double_outer  # 170 mm

# Punkty odniesienia w mm (kanoniczny układ tarczy): 20 góra, 6 prawo, 3 dół, 11 lewo.
BOARD_PTS = np.array([[0, R], [R, 0], [0, -R], [-R, 0]], dtype=np.float32)
LABELS = ["20", "6", "3", "11"]
# Trapez w obrazie symulujący ujęcie pod kątem (top, right, bottom, left).
IMG_QUAD = np.array([[400, 120], [830, 380], [430, 720], [110, 360]], dtype=np.float32)

# Prawdziwa homografia board mm -> image px.
H_B2I = cv2.getPerspectiveTransform(BOARD_PTS, IMG_QUAD)


def _project(x_mm: float, y_mm: float) -> tuple[float, float]:
    q = H_B2I @ np.array([x_mm, y_mm, 1.0])
    return float(q[0] / q[2]), float(q[1] / q[2])


def test_reference_points_on_main_axes():
    assert reference_board_point("20", BOARD) == pytest.approx((0.0, R))
    assert reference_board_point("6", BOARD) == pytest.approx((R, 0.0), abs=1e-6)
    assert reference_board_point("3", BOARD) == pytest.approx((0.0, -R), abs=1e-6)
    assert reference_board_point("11", BOARD) == pytest.approx((-R, 0.0), abs=1e-6)


def test_homography_roundtrip_recovers_board_coords():
    image_points = {lab: tuple(IMG_QUAD[i]) for i, lab in enumerate(LABELS)}
    cam = calibrate_camera_from_points("cam0", (1280, 720), image_points, BOARD)
    H = cam.homography_matrix()
    # Punkty wewnętrzne rzutowane przez prawdziwą homografię wracają do mm.
    for x, y in [(0, 0), (0, 103), (50, -30), (-120, 40)]:
        px = _project(x, y)
        bx, by = image_to_board(H, px)
        assert bx == pytest.approx(x, abs=1e-3)
        assert by == pytest.approx(y, abs=1e-3)


def test_center_px_is_image_of_bull():
    image_points = {lab: tuple(IMG_QUAD[i]) for i, lab in enumerate(LABELS)}
    cam = calibrate_camera_from_points("cam0", (1280, 720), image_points, BOARD)
    assert cam.center_px == pytest.approx(_project(0.0, 0.0), abs=1.0)


def test_scoring_under_perspective_triple_20():
    """Rzut w środek triple 20 (board (0,103)) po przejściu przez perspektywę -> T20."""
    image_points = {lab: tuple(IMG_QUAD[i]) for i, lab in enumerate(LABELS)}
    calib = build_calibration_from_points(BOARD, {"cam0": ((1280, 720), image_points)})
    assert calib.sector20_offset_deg == 0.0
    H = calib.cameras["cam0"].homography_matrix()
    bx, by = image_to_board(H, _project(0.0, 103.0))
    hit = score(*cv2_polar(bx, by), BOARD)
    assert hit.sector == 20 and hit.ring == "triple" and hit.score == 60


def cv2_polar(x, y):
    from dartscore.geometry import cartesian_to_polar
    return cartesian_to_polar(x, y)


def test_requires_four_points():
    from dartscore.errors import BoardNotDetected
    with pytest.raises(BoardNotDetected):
        build_calibration_from_points(BOARD, {"cam0": ((1280, 720), {"20": (1, 2), "6": (3, 4)})})

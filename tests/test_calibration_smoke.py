"""Testy dymne kalibracji + pełnego pipeline na klatkach syntetycznych.

Sprawdzają, że na czystym renderze:
  * wykrywany jest środek tarczy i cyfra "20" (offset orientacji),
  * pełny pipeline zwraca poprawną punktację dla znanego rzutu (triple 20).
"""

from __future__ import annotations

import pytest

from dartscore.config import load_board_config
from dartscore.calibration.board_calibrator import BoardCalibrator
from dartscore.pipeline import ThrowPipeline
from examples.synthetic import render_empty_board, synthetic_throw_frames

BOARD = load_board_config()


def _circular_diff(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


@pytest.mark.parametrize("offset", [0.0, 18.0, 36.0])
def test_orientation_detects_sector20(offset):
    frames = {cid: render_empty_board(offset_deg=offset) for cid in ("cam0", "cam1", "cam2")}
    calib = BoardCalibrator(BOARD).calibrate(frames)
    # Detekcja "20" z krokiem próbkowania 6° -> tolerancja jednego kroku.
    assert _circular_diff(calib.sector20_offset_deg, offset) <= 6.0


def test_board_center_detected_near_image_center():
    img = render_empty_board(offset_deg=0.0)
    disc = BoardCalibrator(BOARD).detect_board_disc(img)
    h, w = img.shape[:2]
    assert disc.center_px[0] == pytest.approx(w / 2.0, abs=5.0)
    assert disc.center_px[1] == pytest.approx(h / 2.0, abs=5.0)


def test_full_pipeline_triple_20():
    calib_frames = {cid: render_empty_board(offset_deg=0.0) for cid in ("cam0", "cam1", "cam2")}
    calibration = BoardCalibrator(BOARD).calibrate(calib_frames)

    before, after = synthetic_throw_frames(tip_angle_deg=0.0, tip_radius_mm=103.0, offset_deg=0.0)
    pipeline = ThrowPipeline(BOARD, calibration)
    result = pipeline.process_pair(before, after)

    assert result.hit.sector == 20
    assert result.hit.ring == "triple"
    assert result.hit.score == 60
    assert result.fused.confidence > 0.0

"""Testy korekcji dystorsji (undistort) i wizualizacji siatki tarczy."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from dartscore.config import load_board_config
from dartscore.calibration.lens import LensIntrinsics, undistort_points, undistort_image
from dartscore.calibration.point_calibrator import calibrate_camera_from_points
from dartscore.calibration.overlay import draw_board_overlay

BOARD = load_board_config()

# Syntetyczna kamera z wyraźną dystorsją beczkowatą (k1 < 0).
K = [[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]]
DIST = [-0.30, 0.10, 0.0, 0.0, 0.0]
INTR = LensIntrinsics(camera_matrix=K, dist_coeffs=DIST)


def _distort_pixels(ideal_px: np.ndarray) -> np.ndarray:
    """Zamień idealne (wyprostowane) piksele na zdystortowane wg modelu kamery."""
    Km = np.array(K)
    norm = np.column_stack([(ideal_px[:, 0] - Km[0, 2]) / Km[0, 0], (ideal_px[:, 1] - Km[1, 2]) / Km[1, 1]])
    obj = np.column_stack([norm, np.ones(len(norm))]).astype(np.float64)
    proj, _ = cv2.projectPoints(obj, np.zeros(3), np.zeros(3), Km, np.array(DIST))
    return proj.reshape(-1, 2)


def test_undistort_points_recovers_ideal():
    ideal = np.array([[640, 360], [200, 150], [1100, 600], [300, 650]], dtype=np.float64)
    distorted = _distort_pixels(ideal)
    # Dystorsja faktycznie przesuwa punkty (poza środkiem).
    assert np.linalg.norm(distorted[1] - ideal[1]) > 2.0
    recovered = undistort_points(distorted, INTR)
    assert np.allclose(recovered, ideal, atol=0.5)


def test_undistort_image_preserves_size():
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    out = undistort_image(img, INTR)
    assert out.shape == img.shape


def test_point_calibration_with_intrinsics_stores_them():
    pts = {"20": (400, 120), "6": (830, 380), "3": (430, 720), "11": (110, 360)}
    cam = calibrate_camera_from_points("cam0", (1280, 720), pts, BOARD, intrinsics=INTR)
    assert cam.camera_matrix == K
    assert cam.dist_coeffs == DIST
    assert cam.intrinsics() is not None


def test_overlay_draws_grid():
    pts = {"20": (400, 120), "6": (830, 380), "3": (430, 720), "11": (110, 360)}
    cam = calibrate_camera_from_points("cam0", (950, 820), pts, BOARD)
    canvas = np.zeros((820, 950, 3), dtype=np.uint8)
    out = draw_board_overlay(canvas, cam.homography_matrix(), BOARD)
    assert out.shape == canvas.shape
    assert int((out > 0).any(axis=2).sum()) > 1000  # siatka faktycznie narysowana

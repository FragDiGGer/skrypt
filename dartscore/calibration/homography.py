"""Homografia obraz kamery -> płaszczyzna tarczy (współrzędne w mm).

Dla kamer bocznych (ustawienie typu Autodarts) każda kamera widzi tarczę pod
kątem, więc mapowanie piksel->tarcza to pełna homografia perspektywiczna 3x3.
Homografię wyznaczamy z punktów odniesienia wykrytych na tarczy (np. cztery
punkty na krawędzi pola double pod znanymi kątami) i zapisujemy w kalibracji.

Dla klatek syntetycznych / widoku czołowego homografia redukuje się do
przekształcenia podobieństwa (przesunięcie + skala + obrót), które również
zapisujemy jako macierz 3x3 — te same funkcje działają w obu przypadkach.
"""

from __future__ import annotations

import cv2
import numpy as np


def find_homography_image_to_board(
    image_points: np.ndarray, board_points_mm: np.ndarray
) -> np.ndarray:
    """Wyznacz H (3x3) mapujące piksele obrazu na mm w płaszczyźnie tarczy.

    Args:
        image_points: (N,2) współrzędne px punktów odniesienia (N>=4).
        board_points_mm: (N,2) odpowiadające współrzędne w mm układu tarczy.
    """
    image_points = np.asarray(image_points, dtype=np.float64).reshape(-1, 1, 2)
    board_points_mm = np.asarray(board_points_mm, dtype=np.float64).reshape(-1, 1, 2)
    h, _ = cv2.findHomography(image_points, board_points_mm, method=0)
    if h is None:
        raise ValueError("Nie udało się wyznaczyć homografii z podanych punktów")
    return h


def similarity_homography(
    center_px: tuple[float, float],
    px_per_mm: float,
    rotation_deg: float = 0.0,
) -> np.ndarray:
    """Zbuduj H (3x3) image->board dla widoku czołowego (bez perspektywy).

    Odwzorowuje: piksel -> (mm), z osią Y skierowaną W GÓRĘ w układzie tarczy
    (obraz ma Y w dół, więc odwracamy znak). Przydatne dla syntetyków i szybkiej
    kalibracji widoku z góry.
    """
    cx, cy = center_px
    s = 1.0 / px_per_mm
    a = np.deg2rad(rotation_deg)
    cos, sin = np.cos(a), np.sin(a)
    # (px - c) -> skala -> obrót -> odwrócenie Y.
    # x_mm =  s*( cos*(px-cx) + sin*(py-cy))
    # y_mm = -s*(-sin*(px-cx) + cos*(py-cy))   (minus bo Y obrazu rośnie w dół)
    h = np.array(
        [
            [s * cos, s * sin, -s * (cos * cx + sin * cy)],
            [s * sin, -s * cos, -s * (sin * cx - cos * cy)],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return h


def image_to_board(h: np.ndarray, point_px: tuple[float, float]) -> tuple[float, float]:
    """Zastosuj homografię do pojedynczego punktu: px -> (x_mm, y_mm)."""
    p = np.array([point_px[0], point_px[1], 1.0], dtype=np.float64)
    q = h @ p
    return float(q[0] / q[2]), float(q[1] / q[2])


def board_to_image(h: np.ndarray, point_mm: tuple[float, float]) -> tuple[float, float]:
    """Odwrotność image_to_board: (x_mm, y_mm) -> px (przydatne w syntetykach/wizualizacji)."""
    h_inv = np.linalg.inv(h)
    p = np.array([point_mm[0], point_mm[1], 1.0], dtype=np.float64)
    q = h_inv @ p
    return float(q[0] / q[2]), float(q[1] / q[2])

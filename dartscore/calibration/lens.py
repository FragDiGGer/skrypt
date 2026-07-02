"""Korekcja dystorsji obiektywu (beczka) — opcjonalna, per kamera.

Kamery OV9732 bywają szerokokątne i wprowadzają dystorsję, która wygina proste
linie przy krawędziach i psuje dokładność przy pierścieniu double. Wyznaczamy
parametry wewnętrzne kamery (macierz K + współczynniki dystorsji) ze zdjęć
szachownicy, a następnie prostujemy obraz przed detekcją i kalibracją tarczy.

To jest KROK OPCJONALNY: bez intrinsics moduł działa jak dotąd (bez prostowania).
Aby włączyć, zrób po kilka zdjęć szachownicy z każdej kamery (patrz calibrate_lens).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..errors import BoardNotDetected


@dataclass(frozen=True)
class LensIntrinsics:
    """Parametry wewnętrzne kamery: macierz K (3x3) i współczynniki dystorsji."""

    camera_matrix: list[list[float]]
    dist_coeffs: list[float]

    def K(self) -> np.ndarray:
        return np.asarray(self.camera_matrix, dtype=np.float64)

    def D(self) -> np.ndarray:
        return np.asarray(self.dist_coeffs, dtype=np.float64)


def calibrate_lens(
    images: list[np.ndarray],
    pattern_size: tuple[int, int] = (9, 6),
) -> LensIntrinsics:
    """Wyznacz intrinsics ze zdjęć szachownicy (róg wewnętrzny = pattern_size).

    Zrób 10–20 zdjęć wydrukowanej szachownicy pod różnymi kątami/pozycjami,
    wypełniającej kadr. Zwraca LensIntrinsics do zapisania w kalibracji kamery.
    """
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0 : pattern_size[0], 0 : pattern_size[1]].T.reshape(-1, 2)
    obj_points, img_points = [], []
    img_size = None
    for img in images:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        img_size = gray.shape[::-1]
        found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
        if not found:
            continue
        corners = cv2.cornerSubPix(
            gray, corners, (11, 11), (-1, -1),
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
        )
        obj_points.append(objp)
        img_points.append(corners)
    if len(obj_points) < 3:
        raise BoardNotDetected(
            f"Za mało zdjęć z wykrytą szachownicą ({len(obj_points)}); potrzeba >= 3 dobrych ujęć"
        )
    ret, K, dist, _, _ = cv2.calibrateCamera(obj_points, img_points, img_size, None, None)
    return LensIntrinsics(camera_matrix=K.tolist(), dist_coeffs=dist.ravel().tolist())


def undistort_image(image: np.ndarray, intr: LensIntrinsics) -> np.ndarray:
    """Wyprostuj obraz (zachowuje rozmiar; K pozostaje bez zmian)."""
    return cv2.undistort(image, intr.K(), intr.D())


def undistort_points(points: np.ndarray, intr: LensIntrinsics) -> np.ndarray:
    """Przelicz punkty px z obrazu zdystortowanego na wyprostowany (te same px)."""
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 1, 2)
    out = cv2.undistortPoints(pts, intr.K(), intr.D(), P=intr.K())
    return out.reshape(-1, 2)

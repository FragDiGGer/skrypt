"""Wyznaczenie końcówki grota lotki (tip detection) — priorytet dokładności.

Metoda (odporna na szum, z dokładnością subpikselową):
  1. Maska nowej lotki z różnicy tła (BackgroundModel).
  2. Największy kontur = sylwetka lotki.
  3. Dopasowanie osi trzonka metodą PCA / cv2.fitLine (kierunek subpikselowy).
  4. Rzut punktów konturu na oś -> dwa skrajne końce; grot to koniec BLIŻSZY
     środkowi tarczy (grot wchodzi w tarczę, lotka wystaje na zewnątrz).
  5. Pewność detekcji z wydłużenia sylwetki (im bardziej liniowa, tym pewniej).

Occlusion: jeśli maska jest pusta/zbyt mała (grot zasłonięty), zwracamy
found=False i ta kamera jest pomijana w fuzji.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class TipDetection:
    """Wynik detekcji grota w jednej kamerze (współrzędne w px obrazu)."""

    found: bool
    tip_px: Optional[tuple[float, float]]
    confidence: float
    axis_dir: Optional[tuple[float, float]] = None  # kierunek osi lotki (jednostkowy)


class TipDetector:
    """Detektor końcówki grota działający na masce różnicy tła."""

    def __init__(self, min_area_px: float = 40.0, min_elongation: float = 2.0) -> None:
        self.min_area_px = min_area_px
        self.min_elongation = min_elongation

    def detect(
        self,
        foreground_mask: np.ndarray,
        board_center_px: tuple[float, float],
    ) -> TipDetection:
        """Znajdź grot na masce; grot = skrajny punkt osi bliższy środkowi tarczy."""
        contours, _ = cv2.findContours(foreground_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if not contours:
            return TipDetection(found=False, tip_px=None, confidence=0.0)

        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        if area < self.min_area_px:
            return TipDetection(found=False, tip_px=None, confidence=0.0)

        pts = contour.reshape(-1, 2).astype(np.float64)

        # Oś trzonka: fitLine daje subpikselowy kierunek i punkt na osi.
        vx, vy, x0, y0 = (float(v) for v in cv2.fitLine(pts.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).flatten())
        axis = np.array([vx, vy], dtype=np.float64)
        origin = np.array([x0, y0], dtype=np.float64)

        # Rzut punktów na oś -> parametry t; skrajne końce sylwetki.
        t = (pts - origin) @ axis
        end_a = origin + axis * float(t.min())
        end_b = origin + axis * float(t.max())

        center = np.array(board_center_px, dtype=np.float64)
        tip = end_a if np.linalg.norm(end_a - center) < np.linalg.norm(end_b - center) else end_b

        confidence = self._confidence(pts, axis)
        if confidence <= 0.0:
            return TipDetection(found=False, tip_px=None, confidence=0.0)

        return TipDetection(
            found=True,
            tip_px=(float(tip[0]), float(tip[1])),
            confidence=confidence,
            axis_dir=(float(axis[0]), float(axis[1])),
        )

    def _confidence(self, pts: np.ndarray, axis: np.ndarray) -> float:
        """Pewność z wydłużenia sylwetki: rozrzut wzdłuż osi vs. prostopadle."""
        centered = pts - pts.mean(axis=0)
        along = centered @ axis
        perp = centered @ np.array([-axis[1], axis[0]])
        std_along = float(along.std()) + 1e-6
        std_perp = float(perp.std()) + 1e-6
        elongation = std_along / std_perp
        if elongation < self.min_elongation:
            return 0.0
        # Mapowanie wydłużenia na (0,1): nasyca się dla bardzo liniowych kształtów.
        return float(max(0.0, min(1.0, 1.0 - 1.0 / elongation)))

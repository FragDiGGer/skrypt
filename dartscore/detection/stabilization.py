"""Detekcja ustabilizowania się lotki po wbiciu (lotka drga zanim znieruchomieje).

Odczyt pozycji grota wykonujemy dopiero, gdy ruch między kolejnymi klatkami
spadnie poniżej progu przez zadaną liczbę klatek — inaczej odczyt byłby obarczony
błędem drgań trzonka.
"""

from __future__ import annotations

import cv2
import numpy as np


class MotionStabilizer:
    """Śledzi ruch między klatkami i sygnalizuje, gdy lotka znieruchomiała."""

    def __init__(self, motion_threshold: float = 0.002, stable_frames: int = 3) -> None:
        # motion_threshold: frakcja zmienionych pikseli uznawana za "ruch".
        self.motion_threshold = motion_threshold
        self.stable_frames = stable_frames
        self._prev_gray: np.ndarray | None = None
        self._still_count = 0

    @staticmethod
    def _gray(frame: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

    def reset(self) -> None:
        self._prev_gray = None
        self._still_count = 0

    def motion_level(self, frame: np.ndarray) -> float:
        """Zwróć frakcję pikseli zmienionych względem poprzedniej klatki [0,1]."""
        gray = self._gray(frame)
        if self._prev_gray is None:
            self._prev_gray = gray
            return 1.0
        diff = cv2.absdiff(gray, self._prev_gray)
        _, mask = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        self._prev_gray = gray
        return float(np.count_nonzero(mask)) / float(mask.size)

    def update(self, frame: np.ndarray) -> bool:
        """Podaj kolejną klatkę; zwróć True, gdy lotka jest ustabilizowana."""
        level = self.motion_level(frame)
        if level <= self.motion_threshold:
            self._still_count += 1
        else:
            self._still_count = 0
        return self._still_count >= self.stable_frames

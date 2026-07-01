"""Model tła / różnica klatek do izolacji NOWO pojawiającej się lotki.

Idea: utrzymujemy obraz tła sprzed rzutu (tarcza z ewentualnymi wcześniej wbitymi
lotkami). Po trafieniu odejmujemy tło od bieżącej klatki — w masce zostaje tylko
nowa lotka, bez wpływu lotek już tkwiących w tarczy. Po odczycie aktualizujemy
tło, aby kolejny rzut porównywać do stanu z nową lotką.
"""

from __future__ import annotations

import cv2
import numpy as np


class BackgroundModel:
    """Prosty model tła oparty o zapamiętaną klatkę referencyjną.

    Świadomie prosty (deterministyczny) — realny system może podmienić to na
    akumulowaną średnią / MOG2; interfejs (update/foreground_mask) pozostaje ten sam.
    """

    def __init__(self, diff_threshold: int = 25, open_ksize: int = 3) -> None:
        self.diff_threshold = diff_threshold
        self.open_ksize = open_ksize
        self._background: np.ndarray | None = None

    @staticmethod
    def _gray(frame: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame

    def reset(self, frame: np.ndarray) -> None:
        """Ustaw klatkę referencyjną (stan tarczy sprzed rzutu)."""
        self._background = self._gray(frame).astype(np.uint8)

    def update(self, frame: np.ndarray) -> None:
        """Zaktualizuj tło do bieżącego stanu (po odczytaniu nowej lotki)."""
        self._background = self._gray(frame).astype(np.uint8)

    @property
    def is_initialized(self) -> bool:
        return self._background is not None

    def foreground_mask(self, frame: np.ndarray) -> np.ndarray:
        """Maska binarna (uint8 0/255) obszaru różniącego się od tła."""
        if self._background is None:
            raise RuntimeError("BackgroundModel nie ma tła — wywołaj reset(frame) najpierw")
        cur = self._gray(frame)
        diff = cv2.absdiff(cur, self._background)
        _, mask = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        if self.open_ksize > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (self.open_ksize, self.open_ksize))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        return mask

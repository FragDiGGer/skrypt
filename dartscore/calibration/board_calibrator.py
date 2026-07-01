"""Kalibracja tarczy: środek + orientacja (przez OCR sektora 20) + homografia.

Przepływ (na klatkach pustej tarczy z każdej z 3 kamer):
  1. Wykryj środek i promień tarczy (największy okrąg pola punktowego).
  2. Zbuduj wstępną homografię obraz->tarcza (mm) — dla widoku czołowego jest to
     przekształcenie podobieństwa; dla kamer bocznych podmień na homografię z
     punktów odniesienia (find_homography_image_to_board).
  3. Rozpoznaj cyfrę "20" na pierścieniu numerycznym i wyznacz jej kąt względem
     środka -> to jest sector20_offset_deg (offset orientacyjny). Pozostałe
     sektory NIE są wykrywane osobno — wynikają obliczeniowo co 18°.

Detekcja jest celowo prosta i odporna na czyste klatki syntetyczne (patrz
examples/synthetic.py); progi/parametry do dostrojenia po dostarczeniu realnych
nagrań. Rozpoznawanie cyfr jest wtykowe (DigitRecognizer).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from ..config import BoardConfig
from ..errors import BoardNotDetected
from ..geometry import polar_to_cartesian
from .digit_ocr import DigitRecognizer, TemplateMatcher
from .homography import similarity_homography, board_to_image
from .store import Calibration, CameraCalibration


@dataclass
class _BoardDisc:
    center_px: tuple[float, float]
    radius_px: float


class BoardCalibrator:
    """Wyznacza Calibration z klatek pustej tarczy."""

    def __init__(
        self,
        board: BoardConfig,
        recognizer: Optional[DigitRecognizer] = None,
        number_ring_mm: float = 195.0,
        orientation_step_deg: float = 6.0,
    ) -> None:
        self.board = board
        self.recognizer = recognizer or TemplateMatcher()
        # Promień, na którym leżą cyfry (tuż poza polem double).
        self.number_ring_mm = number_ring_mm
        self.orientation_step_deg = orientation_step_deg

    # -- detekcja tarczy -----------------------------------------------------

    def detect_board_disc(self, image: np.ndarray) -> _BoardDisc:
        """Znajdź środek i promień pola punktowego (największy jasny okrąg)."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        # Tarcza jako największy spójny obszar na tle — próg Otsu + największy kontur.
        _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise BoardNotDetected("Nie znaleziono konturu tarczy na obrazie")
        biggest = max(contours, key=cv2.contourArea)
        (cx, cy), radius = cv2.minEnclosingCircle(biggest)
        if radius < 1.0:
            raise BoardNotDetected("Wykryty obszar tarczy jest zbyt mały")
        return _BoardDisc(center_px=(float(cx), float(cy)), radius_px=float(radius))

    # -- orientacja (OCR sektora 20) ----------------------------------------

    def detect_orientation(self, image: np.ndarray, h_provisional: np.ndarray) -> tuple[float, float]:
        """Zwróć (sector20_offset_deg, pewność) przez OCR pierścienia numerycznego.

        Próbkujemy obręcz na promieniu number_ring_mm dla kątów co
        orientation_step_deg, klasyfikujemy każdy wycinek i wybieramy kąt o
        najwyższej pewności rozpoznania cyfry "20".
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        best_angle: Optional[float] = None
        best_conf = -1.0
        half = self._patch_half_px(h_provisional)

        angle = 0.0
        while angle < 360.0:
            x_mm, y_mm = polar_to_cartesian(angle, self.number_ring_mm)
            px, py = board_to_image(h_provisional, (x_mm, y_mm))
            patch = self._crop(gray, px, py, half)
            if patch is not None:
                label, conf = self.recognizer.classify(patch)
                if label == 20 and conf > best_conf:
                    best_conf = conf
                    best_angle = angle
            angle += self.orientation_step_deg

        if best_angle is None:
            raise BoardNotDetected("Nie rozpoznano cyfry '20' na pierścieniu numerycznym")
        return best_angle, max(0.0, best_conf)

    def _patch_half_px(self, h_provisional: np.ndarray) -> int:
        """Połowa boku wycinka cyfry w px (~20 mm szerokości cyfry)."""
        p0 = board_to_image(h_provisional, (0.0, self.number_ring_mm))
        p1 = board_to_image(h_provisional, (14.0, self.number_ring_mm))
        return max(8, int(round(np.hypot(p1[0] - p0[0], p1[1] - p0[1]))))

    @staticmethod
    def _crop(gray: np.ndarray, px: float, py: float, half: int) -> Optional[np.ndarray]:
        x, y = int(round(px)), int(round(py))
        h, w = gray.shape[:2]
        if x - half < 0 or y - half < 0 or x + half >= w or y + half >= h:
            return None
        return gray[y - half : y + half, x - half : x + half]

    # -- pełna kalibracja ----------------------------------------------------

    def calibrate_camera(self, camera_id: str, image: np.ndarray) -> tuple[CameraCalibration, float]:
        """Skalibruj pojedynczą kamerę; zwróć (CameraCalibration, offset_z_tej_kamery)."""
        disc = self.detect_board_disc(image)
        # Skala: promień pola double odpowiada double_outer w mm.
        px_per_mm = disc.radius_px / self.board.rings.double_outer
        h_prov = similarity_homography(disc.center_px, px_per_mm, rotation_deg=0.0)
        offset, _conf = self.detect_orientation(image, h_prov)
        h, w = image.shape[:2]
        cam = CameraCalibration(
            camera_id=camera_id,
            homography=h_prov.tolist(),
            center_px=disc.center_px,
            px_per_mm=px_per_mm,
            image_size=(int(w), int(h)),
        )
        return cam, offset

    def calibrate(self, images: dict[str, np.ndarray]) -> Calibration:
        """Skalibruj układ z klatek pustej tarczy (mapa camera_id -> obraz).

        Offset orientacyjny bierzemy jako medianę z kamer, które pewnie
        rozpoznały "20" (redundancja). Homografie zapisujemy per kamera.
        """
        if not images:
            raise BoardNotDetected("Brak obrazów do kalibracji")

        cameras: dict[str, CameraCalibration] = {}
        offsets: list[float] = []
        for cam_id, img in images.items():
            cam, offset = self.calibrate_camera(cam_id, img)
            cameras[cam_id] = cam
            offsets.append(offset)

        sector20_offset = float(np.median(offsets)) if offsets else 0.0
        return Calibration(
            sector20_offset_deg=sector20_offset,
            cameras=cameras,
            metadata={"num_cameras": len(cameras), "per_camera_offset_deg": offsets},
        )

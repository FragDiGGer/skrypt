"""Orkiestracja: klatki z 3 kamer -> pozycja grota -> Hit.

To jest czyste API domenowe (bez HTTP), więc daje się testować niezależnie od
warstwy transportu. Warstwa serwisu (service/api.py) tylko opakowuje ten pipeline.

Użycie (jednostrzałowe, stateless):
    result = pipeline.process_pair(before_frames, after_frames)
    print(result.hit.to_score_dict())

Użycie strumieniowe:
    pipeline.set_reference(before_frames)   # stan tarczy sprzed rzutu
    ... nowa lotka wbita ...
    result = pipeline.process_throw(after_frames)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .config import BoardConfig, CamerasConfig
from .calibration.store import Calibration
from .calibration.homography import image_to_board
from .detection.background import BackgroundModel
from .detection.tip_detector import TipDetector
from .fusion.triangulate import BoardObservation, FusedPosition, fuse_observations
from .scoring import Hit, score
from .errors import CameraOffline, NotCalibrated


@dataclass
class ThrowResult:
    """Wynik rzutu: punktacja + uzgodniona pozycja (do UI / diagnostyki)."""

    hit: Hit
    fused: FusedPosition


class ThrowPipeline:
    """Łączy detekcję, fuzję i punktację w oparciu o zapisaną kalibrację."""

    def __init__(
        self,
        board: BoardConfig,
        calibration: Calibration,
        cameras: Optional[CamerasConfig] = None,
        tip_detector: Optional[TipDetector] = None,
    ) -> None:
        if not calibration.cameras:
            raise NotCalibrated("Kalibracja nie zawiera żadnej kamery")
        # Offset orientacji z kalibracji trafia do geometrii punktacji.
        self.board = board.with_offset(calibration.sector20_offset_deg)
        self.calibration = calibration
        self.cameras = cameras
        self.tip_detector = tip_detector or TipDetector()
        self.min_cameras = cameras.min_cameras_for_hit if cameras else 2
        # Model tła per kamera (stan tarczy sprzed rzutu).
        self._backgrounds: dict[str, BackgroundModel] = {
            cid: BackgroundModel() for cid in calibration.cameras
        }

    # -- API strumieniowe ----------------------------------------------------

    def set_reference(self, frames: dict[str, np.ndarray]) -> None:
        """Ustaw stan odniesienia (tarcza sprzed rzutu) dla każdej kamery."""
        for cid, frame in frames.items():
            if cid in self._backgrounds and frame is not None:
                self._backgrounds[cid].reset(frame)

    def process_throw(self, frames: dict[str, np.ndarray]) -> ThrowResult:
        """Przetwórz klatki po trafieniu i zwróć wynik rzutu."""
        observations = self._collect_observations(frames)
        fused = fuse_observations(observations, min_cameras=self.min_cameras)
        hit = score(fused.angle_deg, fused.radius_mm, self.board)
        # Po odczycie aktualizujemy tło do nowego stanu (z wbitą lotką).
        for cid, frame in frames.items():
            if cid in self._backgrounds and frame is not None:
                self._backgrounds[cid].update(frame)
        return ThrowResult(hit=hit, fused=fused)

    # -- API jednostrzałowe --------------------------------------------------

    def process_pair(
        self, before: dict[str, np.ndarray], after: dict[str, np.ndarray]
    ) -> ThrowResult:
        """Stateless: podaj klatki przed i po rzucie, otrzymaj wynik."""
        self.set_reference(before)
        return self.process_throw(after)

    # -- wewnętrzne ----------------------------------------------------------

    def _collect_observations(self, frames: dict[str, np.ndarray]) -> list[BoardObservation]:
        observations: list[BoardObservation] = []
        for cid, cam_calib in self.calibration.cameras.items():
            frame = frames.get(cid)
            if frame is None:
                # Kamera offline: pomijamy ją, o ile pozostałe wystarczą (sprawdzi fuzja).
                continue
            bg = self._backgrounds[cid]
            if not bg.is_initialized:
                raise CameraOffline(cid, f"Brak stanu odniesienia dla kamery '{cid}'")
            mask = bg.foreground_mask(frame)
            det = self.tip_detector.detect(mask, cam_calib.center_px)
            if not det.found or det.tip_px is None:
                # Grot zasłonięty / brak detekcji w tej kamerze -> pomijamy.
                continue
            x_mm, y_mm = image_to_board(cam_calib.homography_matrix(), det.tip_px)
            observations.append(
                BoardObservation(camera_id=cid, x_mm=x_mm, y_mm=y_mm, confidence=det.confidence)
            )
        return observations

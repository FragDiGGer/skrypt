"""Trwały zapis/odczyt kalibracji (JSON).

Kalibracja jest jednorazowa/okresowa (tarcza i kamery są sztywno zamontowane),
więc liczymy ją raz i wczytujemy przy starcie — bez przeliczania przy każdym rzucie.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import numpy as np


@dataclass
class CameraCalibration:
    """Kalibracja jednej kamery: homografia obraz->tarcza (mm) + metadane.

    Homografia jest wyrażona we współrzędnych obrazu WYPROSTOWANEGO (po korekcji
    dystorsji), jeśli kamera ma intrinsics; inaczej w surowych px obrazu.
    """

    camera_id: str
    homography: list[list[float]]           # 3x3, image px -> board mm
    center_px: tuple[float, float]          # środek tarczy (bull) w px
    px_per_mm: float                        # przybliżona skala (diagnostyka)
    image_size: tuple[int, int]             # (width, height)
    # Opcjonalne parametry dystorsji (włączają prostowanie obrazu przed detekcją).
    camera_matrix: Optional[list[list[float]]] = None
    dist_coeffs: Optional[list[float]] = None

    def homography_matrix(self) -> np.ndarray:
        return np.asarray(self.homography, dtype=np.float64)

    def intrinsics(self):
        """Zwróć LensIntrinsics albo None, jeśli kamera nie ma korekcji dystorsji."""
        if self.camera_matrix is None or self.dist_coeffs is None:
            return None
        from .lens import LensIntrinsics

        return LensIntrinsics(camera_matrix=self.camera_matrix, dist_coeffs=self.dist_coeffs)


@dataclass
class Calibration:
    """Pełny stan kalibracji układu (wszystkie kamery + orientacja tarczy)."""

    sector20_offset_deg: float
    cameras: dict[str, CameraCalibration] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sector20_offset_deg": self.sector20_offset_deg,
            "cameras": {cid: asdict(cc) for cid, cc in self.cameras.items()},
            "metadata": self.metadata,
        }


def save_calibration(calib: Calibration, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(calib.to_dict(), fh, indent=2, ensure_ascii=False)


def load_calibration(path: str | Path) -> Calibration:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku kalibracji: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    cameras = {
        cid: CameraCalibration(
            camera_id=cc["camera_id"],
            homography=cc["homography"],
            center_px=tuple(cc["center_px"]),  # type: ignore[arg-type]
            px_per_mm=float(cc["px_per_mm"]),
            image_size=tuple(cc["image_size"]),  # type: ignore[arg-type]
            camera_matrix=cc.get("camera_matrix"),
            dist_coeffs=cc.get("dist_coeffs"),
        )
        for cid, cc in data["cameras"].items()
    }
    return Calibration(
        sector20_offset_deg=float(data["sector20_offset_deg"]),
        cameras=cameras,
        metadata=data.get("metadata", {}),
    )

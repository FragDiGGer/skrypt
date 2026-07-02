"""Kalibracja perspektywiczna z klikanych punktów odniesienia (zalecana dla realnych kamer).

Kamery boczne widzą tarczę pod kątem → obraz koła to elipsa (silna perspektywa),
a nietypowa czcionka cyfr utrudnia auto-OCR. Najpewniejsza metoda to wskazanie
kilku znanych punktów w obrazie i policzenie pełnej homografii perspektywicznej.

Domyślnie używamy 4 punktów: **zewnętrzna krawędź pierścienia double** dla sektorów
**20, 6, 3, 11**. Leżą one dokładnie na głównych osiach tarczy (0°/90°/180°/270°),
więc w znormalizowanym układzie tarczy to góra/prawo/dół/lewo na promieniu
`double_outer`. Homografia (image px → board mm) od razu koduje perspektywę i
orientację — offset sektora 20 wynosi wtedy 0 (nie trzeba osobnego OCR).

Można podać więcej punktów (np. + bull, + inne sektory) — wtedy homografia jest
dopasowana metodą najmniejszych kwadratów (cv2.findHomography).
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from ..config import BoardConfig
from ..errors import BoardNotDetected
from ..geometry import polar_to_cartesian, sector_center_angle
from .homography import find_homography_image_to_board, board_to_image
from .store import Calibration, CameraCalibration

# Domyślny zestaw punktów: double 20/6/3/11 (osie 0/90/180/270°).
DEFAULT_REFERENCE_LABELS: tuple[str, ...] = ("20", "6", "3", "11")


def reference_board_point(label: str, board: BoardConfig, radius_mm: float | None = None) -> tuple[float, float]:
    """Współrzędne mm punktu odniesienia w kanonicznym układzie tarczy (offset 20 = 0).

    Dla etykiety numerycznej sektora bierzemy jego środek kątowy na promieniu
    `radius_mm` (domyślnie zewnętrzna krawędź double). Etykieta "bull" -> (0,0).
    """
    if label == "bull":
        return (0.0, 0.0)
    canonical = board.with_offset(0.0)  # 20 na górze (0°)
    angle = sector_center_angle(int(label), canonical)
    r = board.rings.double_outer if radius_mm is None else radius_mm
    return polar_to_cartesian(angle, r)


def homography_from_points(
    image_points: Mapping[str, Sequence[float]],
    board: BoardConfig,
    radius_mm: float | None = None,
) -> np.ndarray:
    """Zbuduj homografię image px → board mm z mapy {etykieta: (x_px, y_px)}.

    Wymaga min. 4 punktów (perspektywa ma 8 stopni swobody).
    """
    if len(image_points) < 4:
        raise BoardNotDetected(
            f"Kalibracja perspektywiczna wymaga min. 4 punktów, podano {len(image_points)}"
        )
    labels = list(image_points.keys())
    img = np.array([image_points[l] for l in labels], dtype=np.float64)
    board_pts = np.array([reference_board_point(l, board, radius_mm) for l in labels], dtype=np.float64)
    return find_homography_image_to_board(img, board_pts)


def calibrate_camera_from_points(
    camera_id: str,
    image_size: tuple[int, int],
    image_points: Mapping[str, Sequence[float]],
    board: BoardConfig,
    radius_mm: float | None = None,
) -> CameraCalibration:
    """Zbuduj CameraCalibration dla jednej kamery z klikanych punktów."""
    h = homography_from_points(image_points, board, radius_mm)
    # Środek tarczy (bull) w obrazie = obraz punktu (0,0) przez homografię.
    center_px = board_to_image(h, (0.0, 0.0))
    # Przybliżona skala px/mm: z odległości bull -> punkt double na osi 20.
    top_px = board_to_image(h, (0.0, board.rings.double_outer))
    px_per_mm = float(np.hypot(top_px[0] - center_px[0], top_px[1] - center_px[1]) / board.rings.double_outer)
    return CameraCalibration(
        camera_id=camera_id,
        homography=h.tolist(),
        center_px=(float(center_px[0]), float(center_px[1])),
        px_per_mm=px_per_mm,
        image_size=(int(image_size[0]), int(image_size[1])),
    )


def build_calibration_from_points(
    board: BoardConfig,
    cameras: Mapping[str, tuple[tuple[int, int], Mapping[str, Sequence[float]]]],
    radius_mm: float | None = None,
) -> Calibration:
    """Zbuduj pełną Calibration z punktów dla wielu kamer.

    Args:
        cameras: mapa camera_id -> ((width, height), {etykieta: (x_px, y_px)}).

    Orientacja jest zakodowana w homografii (20 na osi 0°), więc
    `sector20_offset_deg = 0`.
    """
    if not cameras:
        raise BoardNotDetected("Brak kamer do kalibracji punktowej")
    cam_calibs = {
        cid: calibrate_camera_from_points(cid, size, pts, board, radius_mm)
        for cid, (size, pts) in cameras.items()
    }
    return Calibration(
        sector20_offset_deg=0.0,
        cameras=cam_calibs,
        metadata={"method": "points", "reference_labels": list(next(iter(cameras.values()))[1].keys())},
    )

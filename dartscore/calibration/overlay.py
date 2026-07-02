"""Wizualizacja kalibracji: rysuje siatkę tarczy na obrazie kamery.

Po kalibracji pozwala naocznie sprawdzić, czy homografia jest poprawna —
rzutujemy geometrię tarczy (pierścienie, granice sektorów, numery, bull) z układu
mm z powrotem do obrazu i nakładamy na klatkę. Jeśli siatka pokrywa się z realną
tarczą, kalibracja jest dobra.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..config import BoardConfig
from ..geometry import polar_to_cartesian, sector_center_angle
from .homography import board_to_image


def draw_board_overlay(
    image: np.ndarray,
    homography: np.ndarray,
    board: BoardConfig,
    number_ring_mm: float = 190.0,
    color: tuple[int, int, int] = (0, 255, 255),
    thickness: int = 2,
) -> np.ndarray:
    """Nałóż siatkę tarczy na kopię obrazu.

    Args:
        image: klatka kamery (BGR).
        homography: homografia image px -> board mm (jak w CameraCalibration).
        board: geometria (z offsetem orientacji z kalibracji).
    """
    out = image.copy()
    r = board.rings

    def to_img(x_mm: float, y_mm: float) -> tuple[int, int]:
        px, py = board_to_image(homography, (x_mm, y_mm))
        return int(round(px)), int(round(py))

    def ring(radius_mm: float, col: tuple[int, int, int], th: int) -> None:
        pts = [to_img(*polar_to_cartesian(a, radius_mm)) for a in range(0, 360, 3)]
        cv2.polylines(out, [np.array(pts, dtype=np.int32)], True, col, th, cv2.LINE_AA)

    # Pierścienie punktacji.
    for rad in (r.bull, r.outer_bull, r.triple_inner, r.triple_outer, r.double_inner, r.double_outer):
        ring(rad, color, thickness)

    # Granice między sektorami (co 18°, przesunięte o pół klina).
    for k in range(len(board.sector_order)):
        boundary = (k * board.sector_span_deg + board.sector_span_deg / 2.0 + board.sector20_offset_deg)
        p1 = to_img(*polar_to_cartesian(boundary, r.outer_bull))
        p2 = to_img(*polar_to_cartesian(boundary, r.double_outer))
        cv2.line(out, p1, p2, color, 1, cv2.LINE_AA)

    # Numery sektorów na obręczy.
    for sector in board.sector_order:
        ang = sector_center_angle(sector, board)
        cx, cy = to_img(*polar_to_cartesian(ang, number_ring_mm))
        cv2.putText(out, str(sector), (cx - 10, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)

    # Środek (bull).
    bx, by = to_img(0.0, 0.0)
    cv2.drawMarker(out, (bx, by), (255, 0, 255), cv2.MARKER_CROSS, 20, 2)
    return out

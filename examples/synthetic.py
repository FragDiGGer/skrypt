"""Generator syntetycznych klatek tarczy (widok czołowy) do demo i testów.

Renderuje:
  * tarczę jako jasny dysk (pole punktowe do promienia double_outer),
  * pierścień numeryczny z cyframi (białe na czarnym tle poza dyskiem) — w tym
    "20" pod zadanym offsetem orientacji,
  * opcjonalnie lotkę jako ciemną linię wchodzącą w tarczę (do detekcji grota).

To NIE jest realistyczny render kamery bocznej — służy wyłącznie do uruchomienia
całego pipeline'u end-to-end bez sprzętu. Konwencja px<->mm jest zgodna z
dartscore.calibration.homography.similarity_homography (rotation=0).
"""

from __future__ import annotations

import cv2
import numpy as np

from dartscore.config import load_board_config, BoardConfig
from dartscore.geometry import polar_to_cartesian, sector_center_angle

# Cyfry na obręczy — pełen komplet dla realizmu; do detekcji wystarcza "20".
_ALL_LABELS = list(range(1, 21))


def _board_to_px(center: tuple[float, float], px_per_mm: float, x_mm: float, y_mm: float):
    """(x_mm, y_mm) [Y w górę] -> (px, py) [Y w dół], zgodnie z similarity_homography."""
    cx, cy = center
    return cx + x_mm * px_per_mm, cy - y_mm * px_per_mm


def render_empty_board(
    offset_deg: float = 0.0,
    size: int = 800,
    px_per_mm: float = 1.8,
    board: BoardConfig | None = None,
    number_ring_mm: float = 195.0,
    labels: list[int] | None = None,
) -> np.ndarray:
    """Zwróć obraz BGR pustej tarczy z cyframi obręczy (sektor 20 pod offset_deg)."""
    board = board or load_board_config()
    labels = _ALL_LABELS if labels is None else labels
    img = np.zeros((size, size, 3), dtype=np.uint8)
    center = (size / 2.0, size / 2.0)

    # Dysk pola punktowego (jasnoszary) — największy kontur dla detekcji środka.
    r_px = int(round(board.rings.double_outer * px_per_mm))
    cv2.circle(img, (int(center[0]), int(center[1])), r_px, (150, 150, 150), -1)

    # Delikatne okręgi pierścieni (statyczne — kasują się przy różnicy tła).
    for edge in (board.rings.bull, board.rings.outer_bull, board.rings.triple_inner,
                 board.rings.triple_outer, board.rings.double_inner, board.rings.double_outer):
        cv2.circle(img, (int(center[0]), int(center[1])), int(round(edge * px_per_mm)), (110, 110, 110), 1)

    # Cyfry na obręczy: każda w środku swojego sektora, "20" pod offset_deg.
    tmp_board = board.with_offset(offset_deg)
    for label in labels:
        angle = sector_center_angle(label, tmp_board)
        x_mm, y_mm = polar_to_cartesian(angle, number_ring_mm)
        px, py = _board_to_px(center, px_per_mm, x_mm, y_mm)
        _draw_centered_text(img, str(label), (px, py))
    return img


def _draw_centered_text(img: np.ndarray, text: str, pos: tuple[float, float]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 1.4, 3
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    org = (int(pos[0] - tw / 2), int(pos[1] + th / 2))
    cv2.putText(img, text, org, font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def add_dart(
    board_img: np.ndarray,
    tip_angle_deg: float,
    tip_radius_mm: float,
    entry_angle_deg: float | None = None,
    px_per_mm: float = 1.8,
    board: BoardConfig | None = None,
) -> np.ndarray:
    """Dorysuj lotkę: ciemna linia od punktu wejścia (poza tarczą) do grota."""
    board = board or load_board_config()
    img = board_img.copy()
    size = img.shape[0]
    center = (size / 2.0, size / 2.0)

    tip_x, tip_y = polar_to_cartesian(tip_angle_deg, tip_radius_mm)
    tip_px = _board_to_px(center, px_per_mm, tip_x, tip_y)

    # Trzonek wychodzi na zewnątrz — lekko z boku, by symulować kąt wejścia.
    entry_angle = tip_angle_deg + 4.0 if entry_angle_deg is None else entry_angle_deg
    ent_x, ent_y = polar_to_cartesian(entry_angle, board.rings.double_outer + 55.0)
    ent_px = _board_to_px(center, px_per_mm, ent_x, ent_y)

    cv2.line(img, (int(ent_px[0]), int(ent_px[1])), (int(tip_px[0]), int(tip_px[1])), (30, 30, 30), 4)
    # Wyraźna końcówka grota.
    cv2.circle(img, (int(tip_px[0]), int(tip_px[1])), 3, (30, 30, 30), -1)
    return img


def synthetic_throw_frames(
    tip_angle_deg: float,
    tip_radius_mm: float,
    camera_ids: tuple[str, ...] = ("cam0", "cam1", "cam2"),
    offset_deg: float = 0.0,
    px_per_mm: float = 1.8,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Zwróć (before, after) — po jednej klatce pustej i z lotką na każdą kamerę."""
    board = load_board_config()
    before: dict[str, np.ndarray] = {}
    after: dict[str, np.ndarray] = {}
    # Różne kąty wejścia lotki symulują 3 kamery patrzące z różnych stron.
    entry_offsets = (-6.0, 0.0, 6.0)
    for cid, eoff in zip(camera_ids, entry_offsets):
        empty = render_empty_board(offset_deg=offset_deg, px_per_mm=px_per_mm, board=board)
        before[cid] = empty
        after[cid] = add_dart(
            empty, tip_angle_deg, tip_radius_mm,
            entry_angle_deg=tip_angle_deg + eoff, px_per_mm=px_per_mm, board=board,
        )
    return before, after

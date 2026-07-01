"""Demo end-to-end na klatkach syntetycznych (bez sprzętu).

Przepływ:
  1. Wygeneruj klatki pustej tarczy dla 3 kamer i skalibruj (wykrycie "20").
  2. Wygeneruj klatki z lotką trafioną w znane miejsce (domyślnie triple 20).
  3. Przepuść przez pipeline i wypisz wynik Hit jako JSON.

Uruchomienie:  python examples/mock_throw.py
Oczekiwany wynik dla T20:  {"sector": 20, "ring": "triple", "score": 60}
"""

from __future__ import annotations

import json

from dartscore.config import load_board_config, load_cameras_config
from dartscore.calibration.board_calibrator import BoardCalibrator
from dartscore.pipeline import ThrowPipeline
from examples.synthetic import render_empty_board, synthetic_throw_frames

# Znany rzut: środek pola triple sektora 20 (kąt 0°, promień w pierścieniu triple).
TIP_ANGLE_DEG = 0.0
TIP_RADIUS_MM = 103.0
BOARD_OFFSET_DEG = 0.0  # tarcza idealnie ustawiona (20 na górze)


def main() -> None:
    board = load_board_config()

    # 1) Kalibracja z klatek pustej tarczy.
    calib_frames = {
        cid: render_empty_board(offset_deg=BOARD_OFFSET_DEG)
        for cid in ("cam0", "cam1", "cam2")
    }
    calibrator = BoardCalibrator(board)
    calibration = calibrator.calibrate(calib_frames)
    print(f"[kalibracja] wykryty offset sektora 20: {calibration.sector20_offset_deg:.2f}°")

    # 2) Klatki rzutu (before/after) dla 3 kamer.
    before, after = synthetic_throw_frames(
        TIP_ANGLE_DEG, TIP_RADIUS_MM, offset_deg=BOARD_OFFSET_DEG
    )

    # 3) Pipeline -> Hit.
    try:
        cameras = load_cameras_config()
    except FileNotFoundError:
        cameras = None
    pipeline = ThrowPipeline(board, calibration, cameras=cameras)
    result = pipeline.process_pair(before, after)

    print("[wynik] pełny Hit:")
    print(json.dumps(result.hit.to_dict(), indent=2, ensure_ascii=False))
    print("[wynik] forma zgodna ze specyfikacją:")
    print(json.dumps(result.hit.to_score_dict(), ensure_ascii=False))
    print(f"[wynik] pewność fuzji: {result.fused.confidence:.2f}, kamery: {result.fused.cameras_used}")


if __name__ == "__main__":
    main()

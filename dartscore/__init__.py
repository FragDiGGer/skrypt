"""dartscore — niezależny moduł detekcji i punktacji tarczy dart z 3 kamer.

Warstwy (każda testowalna niezależnie):
  * config      — wczytanie geometrii/tolerancji i konfiguracji kamer,
  * geometry    — matematyka polar <-> sektor (bez stałych w kodzie),
  * scoring     — (kąt, promień) -> Hit  [rdzeń, w pełni pokryty testami],
  * calibration — środek tarczy + orientacja przez OCR sektora "20" + homografia,
  * detection   — izolacja nowej lotki i wyznaczenie końcówki grota (szkielet),
  * fusion      — połączenie detekcji z 3 kamer w jedną pozycję + confidence,
  * pipeline    — orkiestracja klatki(3) -> Hit.

Warstwa transportu (FastAPI HTTP/WebSocket) żyje w osobnym pakiecie `service`,
aby logikę wizyjną dało się używać i testować bez zależności webowych.
"""

from .config import BoardConfig, CameraConfig, load_board_config, load_cameras_config
from .scoring import Hit, score
from .errors import (
    DartScoreError,
    BoardNotDetected,
    CameraOffline,
    AmbiguousHit,
    NotCalibrated,
)

__all__ = [
    "BoardConfig",
    "CameraConfig",
    "load_board_config",
    "load_cameras_config",
    "Hit",
    "score",
    "DartScoreError",
    "BoardNotDetected",
    "CameraOffline",
    "AmbiguousHit",
    "NotCalibrated",
]

__version__ = "0.1.0"

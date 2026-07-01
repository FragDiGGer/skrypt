"""Typowane wyjątki modułu.

Warstwa API mapuje je na kody HTTP (patrz service/api.py):
    NotCalibrated     -> 409 Conflict
    BoardNotDetected  -> 409 Conflict
    CameraOffline     -> 503 Service Unavailable
    AmbiguousHit      -> 422 Unprocessable Entity
"""


class DartScoreError(Exception):
    """Bazowy wyjątek modułu — pozwala łapać wszystkie błędy domenowe naraz."""


class NotCalibrated(DartScoreError):
    """Próba punktacji zanim wykonano/wczytano kalibrację tarczy."""


class BoardNotDetected(DartScoreError):
    """Nie udało się wykryć tarczy (środka lub pierścienia cyfr) na obrazie."""


class CameraOffline(DartScoreError):
    """Kamera nie dostarczyła klatki (brak sygnału / rozłączona)."""

    def __init__(self, camera_id: str, message: str | None = None) -> None:
        self.camera_id = camera_id
        super().__init__(message or f"Kamera '{camera_id}' jest offline.")


class AmbiguousHit(DartScoreError):
    """Pozycja lotki niejednoznaczna (za mało zgodnych detekcji / duży rozrzut)."""

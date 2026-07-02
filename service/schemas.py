"""Modele pydantic — kontrakt JSON między serwisem a backendem Node/JS."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FrameSet(BaseModel):
    """Zestaw klatek z kamer jako obrazy zakodowane base64 (PNG/JPEG)."""

    frames: dict[str, str] = Field(
        ..., description="Mapa camera_id -> obraz base64 (z prefiksem data URI lub bez)"
    )


class ThrowRequest(BaseModel):
    """Rzut jednostrzałowy: klatki przed i po trafieniu."""

    before: dict[str, str] = Field(..., description="Klatki sprzed rzutu (camera_id -> base64)")
    after: dict[str, str] = Field(..., description="Klatki po trafieniu (camera_id -> base64)")


class CameraPoints(BaseModel):
    """Punkty odniesienia jednej kamery (piksele obrazu natywnego)."""

    image_size: tuple[int, int] = Field(..., description="[szerokość, wysokość] klatki w px")
    points: dict[str, tuple[float, float]] = Field(
        ..., description="Mapa etykieta -> [x_px, y_px]; domyślnie double 20/6/3/11"
    )


class PointsCalibrationRequest(BaseModel):
    """Kalibracja perspektywiczna z klikanych punktów (mapa camera_id -> punkty)."""

    cameras: dict[str, CameraPoints]


class Position(BaseModel):
    angle_deg: float
    radius_mm: float
    x_mm: float
    y_mm: float


class HitResponse(BaseModel):
    """Wynik trafienia zwracany do frontu."""

    sector: Optional[int]
    ring: str
    multiplier: int
    score: int
    confidence: float
    near_boundary: bool
    position: Position
    cameras_used: list[str]


class CalibrationResponse(BaseModel):
    calibrated: bool
    sector20_offset_deg: Optional[float] = None
    cameras: list[str] = Field(default_factory=list)
    message: Optional[str] = None

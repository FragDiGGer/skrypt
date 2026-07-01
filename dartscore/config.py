"""Wczytanie i walidacja konfiguracji z plików YAML.

Wszystkie wymiary geometrii tarczy i tolerancje pochodzą wyłącznie stąd
(`config/board.yaml`) — dzięki temu w kodzie nie ma rozsianych "magic numbers".
Konfiguracja kamer (`config/cameras.yaml`) opisuje sprzęt i próg fuzji.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Domyślna lokalizacja plików konfiguracyjnych względem katalogu repozytorium.
_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOARD_CONFIG = _REPO_ROOT / "config" / "board.yaml"
DEFAULT_CAMERAS_CONFIG = _REPO_ROOT / "config" / "cameras.yaml"


@dataclass(frozen=True)
class RingRadii:
    """Promienie granic pierścieni (mm), konwencja przedziałów [dolna, górna)."""

    bull: float
    outer_bull: float
    triple_inner: float
    triple_outer: float
    double_inner: float
    double_outer: float

    def __post_init__(self) -> None:
        # Promienie muszą rosnąć monotonicznie — inaczej mapowanie na pierścienie
        # byłoby niejednoznaczne.
        seq = [
            self.bull,
            self.outer_bull,
            self.triple_inner,
            self.triple_outer,
            self.double_inner,
            self.double_outer,
        ]
        if any(b <= a for a, b in zip(seq, seq[1:])):
            raise ValueError(f"Promienie pierścieni muszą rosnąć monotonicznie, otrzymano: {seq}")


@dataclass(frozen=True)
class Tolerances:
    """Tolerancje wyłącznie do metryki 'bliskość granicy' (nie zmieniają wyniku)."""

    boundary_angle_deg: float = 1.5
    boundary_radius_mm: float = 2.0


@dataclass(frozen=True)
class BoardConfig:
    """Kompletna geometria tarczy używana przez scoring i geometry."""

    sector_order: tuple[int, ...]
    sector_span_deg: float
    sector20_offset_deg: float
    rings: RingRadii
    tolerances: Tolerances = field(default_factory=Tolerances)

    def __post_init__(self) -> None:
        if len(self.sector_order) != 20:
            raise ValueError(f"sector_order musi mieć 20 elementów, ma {len(self.sector_order)}")
        if set(self.sector_order) != set(range(1, 21)):
            raise ValueError("sector_order musi być permutacją liczb 1..20")
        # 20 sektorów * 18° = 360°.
        if abs(self.sector_span_deg * len(self.sector_order) - 360.0) > 1e-6:
            raise ValueError("sector_span_deg * liczba_sektorów musi wynosić 360°")

    def with_offset(self, sector20_offset_deg: float) -> "BoardConfig":
        """Zwróć kopię z podmienionym offsetem orientacji (wynik kalibracji)."""
        return BoardConfig(
            sector_order=self.sector_order,
            sector_span_deg=self.sector_span_deg,
            sector20_offset_deg=sector20_offset_deg,
            rings=self.rings,
            tolerances=self.tolerances,
        )


@dataclass(frozen=True)
class CameraConfig:
    """Metadane pojedynczej kamery (bez homografii — ta jest w pliku kalibracji)."""

    id: str
    index: int
    resolution: tuple[int, int]
    azimuth_deg: float


@dataclass(frozen=True)
class CamerasConfig:
    cameras: tuple[CameraConfig, ...]
    min_cameras_for_hit: int = 2


def _read_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Nie znaleziono pliku konfiguracji: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Plik konfiguracji {path} musi zawierać mapę na najwyższym poziomie")
    return data


def load_board_config(path: str | Path | None = None) -> BoardConfig:
    """Wczytaj geometrię tarczy z YAML (domyślnie config/board.yaml)."""
    data = _read_yaml(path or DEFAULT_BOARD_CONFIG)
    rings = RingRadii(**data["rings"])
    tol = Tolerances(**data.get("tolerances", {}))
    return BoardConfig(
        sector_order=tuple(int(x) for x in data["sector_order"]),
        sector_span_deg=float(data["sector_span_deg"]),
        sector20_offset_deg=float(data.get("sector20_offset_deg", 0.0)),
        rings=rings,
        tolerances=tol,
    )


def load_cameras_config(path: str | Path | None = None) -> CamerasConfig:
    """Wczytaj konfigurację kamer z YAML (domyślnie config/cameras.yaml)."""
    data = _read_yaml(path or DEFAULT_CAMERAS_CONFIG)
    cams = tuple(
        CameraConfig(
            id=str(c["id"]),
            index=int(c["index"]),
            resolution=tuple(int(v) for v in c["resolution"]),  # type: ignore[arg-type]
            azimuth_deg=float(c.get("azimuth_deg", 0.0)),
        )
        for c in data["cameras"]
    )
    return CamerasConfig(cameras=cams, min_cameras_for_hit=int(data.get("min_cameras_for_hit", 2)))

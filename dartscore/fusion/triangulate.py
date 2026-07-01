"""Uzgodnienie detekcji z 3 kamer w jedną pozycję (kąt, promień) + pewność.

Każda kamera, po zastosowaniu swojej homografii, daje punkt grota we WSPÓLNYM
układzie tarczy (mm). Łączymy je odpornie na błędy:
  * mediana jako estymator odniesienia,
  * odrzucanie outlierów (kamery odległe od mediany > próg),
  * ważona średnia inlierów wg pewności detekcji,
  * metryka pewności wynikowej (zgodność kamer + ich confidence).

Occlusion: kamery bez detekcji po prostu nie wnoszą obserwacji. Jeśli inlierów
jest mniej niż min_cameras, zgłaszamy AmbiguousHit (pozycja niepewna).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..errors import AmbiguousHit
from ..geometry import cartesian_to_polar


@dataclass
class BoardObservation:
    """Obserwacja grota z jednej kamery we współrzędnych tarczy (mm)."""

    camera_id: str
    x_mm: float
    y_mm: float
    confidence: float


@dataclass
class FusedPosition:
    """Uzgodniona pozycja grota na tarczy."""

    x_mm: float
    y_mm: float
    angle_deg: float
    radius_mm: float
    confidence: float
    cameras_used: list[str] = field(default_factory=list)


def fuse_observations(
    observations: list[BoardObservation],
    min_cameras: int = 2,
    outlier_mm: float = 12.0,
) -> FusedPosition:
    """Połącz obserwacje z kamer w jedną pozycję na tarczy.

    Args:
        observations: lista detekcji (jedna na kamerę, która wykryła grot).
        min_cameras: minimalna liczba zgodnych kamer dla pewnego trafienia.
        outlier_mm: maks. odległość od mediany, by uznać kamerę za inlier.
    """
    if not observations:
        raise AmbiguousHit("Brak jakiejkolwiek detekcji grota z kamer")

    pts = np.array([[o.x_mm, o.y_mm] for o in observations], dtype=np.float64)
    confs = np.array([max(0.0, o.confidence) for o in observations], dtype=np.float64)

    # Pojedyncza kamera: zwracamy jej pozycję, ale z obniżoną pewnością.
    if len(observations) == 1:
        if min_cameras > 1:
            raise AmbiguousHit("Tylko jedna kamera wykryła grot — pozycja niepewna")
        return _to_position([observations[0]], pts, confs, single=True)

    # Mediana jako odporny punkt odniesienia; odrzuć kamery zbyt odległe.
    median = np.median(pts, axis=0)
    dist = np.linalg.norm(pts - median, axis=1)
    inlier_mask = dist <= outlier_mm

    inliers = [o for o, keep in zip(observations, inlier_mask) if keep]
    if len(inliers) < min_cameras:
        raise AmbiguousHit(
            f"Zbyt mało zgodnych kamer ({len(inliers)} < {min_cameras}) — rozrzut detekcji zbyt duży"
        )

    in_pts = pts[inlier_mask]
    in_confs = confs[inlier_mask]
    return _to_position(inliers, in_pts, in_confs, single=False)


def _to_position(
    obs: list[BoardObservation], pts: np.ndarray, confs: np.ndarray, single: bool
) -> FusedPosition:
    weights = confs if confs.sum() > 1e-9 else np.ones(len(confs))
    weights = weights / weights.sum()
    x, y = (pts * weights[:, None]).sum(axis=0)
    angle, radius = cartesian_to_polar(float(x), float(y))

    # Pewność: średnia ważona confidence kamer, skorygowana o zgodność (rozrzut)
    # i karę za pojedynczą kamerę.
    mean_conf = float((confs * weights).sum())
    spread = float(np.linalg.norm(pts - pts.mean(axis=0), axis=1).mean()) if len(pts) > 1 else 0.0
    agreement = 1.0 / (1.0 + spread / 5.0)  # 0 mm rozrzutu -> 1.0; rośnie -> maleje
    confidence = mean_conf * agreement * (0.6 if single else 1.0)

    return FusedPosition(
        x_mm=float(x),
        y_mm=float(y),
        angle_deg=angle,
        radius_mm=radius,
        confidence=float(max(0.0, min(1.0, confidence))),
        cameras_used=[o.camera_id for o in obs],
    )

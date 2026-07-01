"""Testy fuzji: mediana/ważenie, odrzucanie outlierów, occlusion, przypadki błędne."""

from __future__ import annotations

import pytest

from dartscore.fusion.triangulate import BoardObservation, fuse_observations
from dartscore.errors import AmbiguousHit


def _obs(cid, x, y, conf=1.0):
    return BoardObservation(camera_id=cid, x_mm=x, y_mm=y, confidence=conf)


def test_three_close_cameras_agree():
    obs = [_obs("cam0", 0.0, 103.0), _obs("cam1", 1.0, 104.0), _obs("cam2", -1.0, 102.0)]
    fused = fuse_observations(obs, min_cameras=2)
    assert fused.radius_mm == pytest.approx(103.0, abs=2.0)
    assert fused.angle_deg == pytest.approx(0.0, abs=2.0)
    assert set(fused.cameras_used) == {"cam0", "cam1", "cam2"}
    assert fused.confidence > 0.5


def test_outlier_camera_is_rejected():
    obs = [_obs("cam0", 0.0, 103.0), _obs("cam1", 1.0, 104.0), _obs("cam2", 80.0, 20.0)]
    fused = fuse_observations(obs, min_cameras=2, outlier_mm=12.0)
    assert "cam2" not in fused.cameras_used
    assert fused.radius_mm == pytest.approx(103.0, abs=3.0)


def test_occlusion_two_of_three_still_works():
    # Tylko dwie kamery wykryły grot (trzecia zasłonięta -> brak obserwacji).
    obs = [_obs("cam0", 0.0, 103.0), _obs("cam1", 0.5, 103.5)]
    fused = fuse_observations(obs, min_cameras=2)
    assert len(fused.cameras_used) == 2


def test_single_camera_below_min_raises():
    with pytest.raises(AmbiguousHit):
        fuse_observations([_obs("cam0", 0.0, 103.0)], min_cameras=2)


def test_single_camera_allowed_with_low_confidence():
    fused = fuse_observations([_obs("cam0", 0.0, 103.0, conf=1.0)], min_cameras=1)
    assert fused.cameras_used == ["cam0"]
    # Pojedyncza kamera -> obniżona pewność (kara 0.6).
    assert fused.confidence < 0.7


def test_empty_observations_raise():
    with pytest.raises(AmbiguousHit):
        fuse_observations([], min_cameras=1)


def test_too_much_spread_raises():
    # Trzy rozjechane detekcje — po odrzuceniu outlierów zostaje < min_cameras.
    obs = [_obs("cam0", 0.0, 103.0), _obs("cam1", 60.0, 30.0), _obs("cam2", -60.0, -30.0)]
    with pytest.raises(AmbiguousHit):
        fuse_observations(obs, min_cameras=2, outlier_mm=12.0)

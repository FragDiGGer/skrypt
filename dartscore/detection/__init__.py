"""Detekcja lotki: izolacja nowej lotki (różnica tła) + wyznaczenie grota."""

from .background import BackgroundModel
from .tip_detector import TipDetector, TipDetection
from .stabilization import MotionStabilizer

__all__ = ["BackgroundModel", "TipDetector", "TipDetection", "MotionStabilizer"]

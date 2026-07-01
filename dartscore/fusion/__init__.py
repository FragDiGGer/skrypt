"""Fuzja pozycji grota z wielu kamer w jedną pozycję na tarczy."""

from .triangulate import BoardObservation, FusedPosition, fuse_observations

__all__ = ["BoardObservation", "FusedPosition", "fuse_observations"]

"""Energy analysis module."""

from .builds_drops import detect_builds_and_drops
from .multiscale import extract_smoothed_energy

__all__ = ["extract_smoothed_energy", "detect_builds_and_drops"]

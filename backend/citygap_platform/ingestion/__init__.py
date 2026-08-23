"""Streaming CityGML ingestion utilities."""

from .inventory import build_archive_inventory
from .profile import detect_archive_profile

__all__ = ["build_archive_inventory", "detect_archive_profile"]

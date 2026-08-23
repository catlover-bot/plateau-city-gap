"""Backward-compatible entry point for the Maizuru primary analysis."""

from pathlib import Path

from .city_config import load_city_config
from .run_city_analysis import run_city_analysis


def main() -> None:
    run_city_analysis(load_city_config(Path("analysis/config/maizuru.yaml")))


if __name__ == "__main__":
    main()

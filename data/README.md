# Data directory

Downloaded data are excluded from Git. Provenance is in [`docs/data-sources.md`](../docs/data-sources.md).
`raw/` holds immutable downloads, `interim/` normalized layers, and `processed/` analysis-ready data.

Verified real inputs as of 2026-08-22 are e-Stat `T001192`, National Land Numerical
Information `P11-2022` and `P04-2020`, and the PLATEAU Maizuru 2025 related-data ZIP.
Run `python -m analysis.scripts.download_real_data` to reproduce the ignored raw files.

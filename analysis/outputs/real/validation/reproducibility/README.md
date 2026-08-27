# CITY GAP validation reproducibility bundle

This bundle contains commands, hashes, algorithm versions, and expected summaries. Large raw OSM and PLATEAU CityGML archives are deliberately not tracked. Place checksum-matching files at the manifest paths, install `.[platform,dev]`, then run `citygap validate reproduce --city maizuru` or `--city fujisawa`.

The command verifies pinned source hashes before analysis and compares the resulting city summary with the tracked expected result. OSM and official datasets are reference sources, not field ground truth.

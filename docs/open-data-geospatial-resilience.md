# Geospatial reference, resilience, safety and mobility sources

This audit was run on 2026-08-28. Its machine-readable evidence is
`analysis/outputs/real/open_data/geospatial_resilience_source_report.json`; the canonical
records and count/hash summary sit beside it. Catalog discovery, source availability and
analysis promotion are separate states. A source with no pilot-city package never creates a
zero-valued or synthetic record.

## Promoted official snapshots

| Source | Official snapshot | Source rows | Pilot canonical records | Use boundary |
|---|---|---:|---:|---|
| [J-SHIS V4 surface-ground data](https://www.j-shis.bosai.go.jp/api-sstruct-meshinfo) | first meshes `5335`, `5339`; CSV dates 2021-03-03 and corrected 2022-05-30 | 44,747 + 93,474 | Maizuru 1,980; Fujisawa 1,084 | Published 250m cells whose parent is an audited 500m mesh. Model attributes, not site measurements or earthquake probability. |
| [NPA 2024 traffic-accident open data](https://www.npa.go.jp/publications/statistics/koutsuu/opendata/2024/opendata_2024.html) | `honhyo_2024.csv` plus schema/codebook workbooks | 290,895 | Maizuru 59; Fujisawa 982 | Historical injury/fatal accidents only; property-only accidents are outside source scope. No denominator, causal effect, risk surface or prediction. |

J-SHIS mesh geometry is decoded as JGD2000/EPSG:4612 and explicitly transformed to
EPSG:4326. `JCODE=0` is coastal water: encoded `AVS=0` / `ARV=0` remains in provenance,
while canonical ground values are null. It is never interpreted as a zero-speed ground
observation. Selection describes the audited full 500m mesh context, not an exact
municipal-boundary aggregate. All 495 Maizuru parent meshes have published cells; 56 of 327
Fujisawa audited parent meshes do not, and are not imputed.

The NPA CSV is CP932 with an exact 68-field contract. World-geodetic fixed-width DMS is
validated before EPSG:4326 conversion. NPA prefecture/municipality codes select `61/202`
for Maizuru and `45/205` for Fujisawa. The 2024 annual file includes event occurrence years
different from the file label; canonical records therefore keep `annual_file_year` and
`occurred_at` separately. Maizuru has 58 points inside the audited mesh context and one
outside; Fujisawa has 978 and four. The five outside-context records remain auditable.

## Researched capabilities not promoted as snapshots

| Capability | Maizuru | Fujisawa | Reason and next gate |
|---|---|---|---|
| [GSI Fundamental Geospatial Data](https://service.gsi.go.jp/kiban/app/help/) file spec 5.3 | `requires_review` | `requires_review` | Registered credentials are required; Survey Act and intended reproduction/use must be reviewed. Current specification uses JGD2024. No bytes were ingested and no GSI/PLATEAU comparison was made. |
| [MLIT pedestrian network catalog](https://ckan.hokonavi.go.jp/dataset/) | `unavailable / outside_coverage` | `unavailable / outside_coverage` | The current 31-package catalog has no pilot-city walking network. Legacy Fujisawa facility barrier-free metadata is not a network. PLATEAU road surfaces stay `plateau_experimental`. |
| [xROAD/JARTIC traffic API](https://www.jartic-open-traffic.org/) | `partial` | `unknown` | A bounded 2026-08-28 21:00 JST probe found three in-context Maizuru CCTV reference points and none for Fujisawa. A one-time absence does not prove no Fujisawa coverage; rolling reference data are not a stable snapshot or official survey result. |
| Official GTFS/GTFS-JP | `unavailable / not_published` | `unavailable / not_published` | Recheck found no stable downloadable official feed. P11 stops are never converted to GTFS. See [GTFS source status](gtfs.md). |

xROAD was queried only for a bounded coverage audit. No polling archive was constructed and
no traffic volume, congestion, capacity or prediction metric is emitted. The paid DRM-PF API
was not used.

## Licence and raw-publication boundary

- J-SHIS uses the [J-SHIS terms](https://www.j-shis.bosai.go.jp/agreement). Derived output
  requires attribution; unchanged or format-converted raw reproduction is not published by
  CITY GAP. Commercial conditions remain review-required.
- NPA uses [Public Data License 1.0](https://www.npa.go.jp/rules/index.html). Attribution and
  an edited/processed notice are required. Project policy still keeps raw CSV/XLSX outside
  public assets.
- GSI is stored as `gsi-survey-act-review`: unknown terms are never treated as permission.
- xROAD is stored as `xroad-api-terms-2025-05`: attribution is required and raw
  redistribution remains unknown in the platform policy.

All five downloaded objects are stored by SHA-256 under ignored `data/raw/open_data/`:
two J-SHIS ZIPs, the NPA main CSV, schema workbook and codebook workbook. Git contains only
the bounded canonical derivatives, source report and summary.

## Rebuild and validation

Run from the repository root:

```bash
python -m analysis.scripts.build_geospatial_resilience_open_data \
  --observed-at 2026-08-28T21:00:00+09:00
python -m pytest \
  backend/tests/test_resilience_open_data.py \
  backend/tests/test_real_geospatial_resilience_open_data.py
```

The builder rediscovers the latest NPA annual page and deterministic reviewed J-SHIS first
mesh archives, then applies HTTPS host allowlists, byte limits, safe ZIP rules, exact schema,
encoding, coordinate, event-time and formula-like-cell gates. Any discovery change requires
review before expected hashes are updated.

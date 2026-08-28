# Municipal open-data analysis

`analysis/scripts/build_municipal_open_data_analysis.py` connects promoted official-source
canonical records to the existing 2025 PLATEAU Urban States for Maizuru and Fujisawa. It
produces internal review evidence, not a public ranking layer or an administrative decision.
The checked-in result contains all 822 audited 500m meshes: 495 in Maizuru and 327 in
Fujisawa. No synthetic record or missing-value zero is introduced.

## Analysis Catalog V2

Migration `022_municipal_open_data_analyses.sql` adds six versioned definitions and records
every dataset dependency as `required`, `optional`, or `enhancement`. Missing required data
makes an analysis `UNAVAILABLE`; satisfied required data enables `BASE`; a definition with
all declared enhancement sources can become `ENHANCED`. Optional context never becomes a
hidden hard dependency. Both pilot cities currently run all six analyses at `BASE` because
qualified official pedestrian, social-participation and/or traffic-volume sources are absent.

| Analysis | Real input and method | Output boundary |
|---|---|---|
| Medical Access V2 | 2020 disclosed census mesh, MHLW 2026 medical points, PLATEAU 2025 spatial model; centroid distance in the city's JGD2011 plane CRS | Hospital/clinic distance drives review candidates. Pharmacy, dental, hospital, clinic, internal-medicine and pediatrics contexts stay separate. The MHLW horizontal datum is undeclared, so distance is `requires_review`; it is not time, acceptance, capacity or shortage. |
| Care Access | 2020 disclosed elderly population, deduplicated MHLW 2026 care establishments, PLATEAU building/experimental transport graph context | A conjunction of city-local distribution thresholds emits `care_access_review_candidate`. It never asserts demand, eligibility, vacancy or care shortage. |
| Future official population spatial comparison | MLIT R6 250m official trial projections deterministically aggregated to their JIS 500m parent | 2025, 2050 and 2070 remain named official trial years. Pre-privacy-aggregation values are internal-only; no best scenario or forecast guarantee is generated. |
| Daytime Activity Context | 2021 Economic Census employee/establishment observations joined to separate MHLW 2026 and P11 2022 distance context | Employees are explicitly not daytime population. `activity_service_gap_candidate` is a review label, not demand, congestion or a policy gap. |
| Earthquake / Ground Context | J-SHIS V4 2020 250m model cells aggregated to 500m | AVS, ARV, microtopography and coastal-null counts are context only. No probability, damage forecast, risk score or Finding is created. |
| Historical Traffic Safety Context | NPA 2024 annual file events aggregated to audited meshes, while occurrence dates remain separate | Event, fatality and injury counts have no traffic-volume denominator. The five outside-context events remain in coverage evidence. No danger/risk Finding is created. |

Candidate thresholds are city-local and recorded verbatim in every Finding. There is no
combined score, severity, cross-city rank, policy priority or automatic recommendation.
Current deterministic output contains 50 unvalidated review candidates:

- Maizuru: medical 10, care 1, activity/service 5.
- Fujisawa: medical 17, care 2, activity/service 15.

Each candidate starts at `new` / `unvalidated`, has null Investigation and Decision IDs, and
requires explicit human triage. The evidence package supplies city-specific Investigation
templates only; it does not create workflow records.

## Spatial linkage and PLATEAU boundary

The audited 500m mesh and current PLATEAU 2025 Urban State remain the primary spatial model.
Official point-to-city links are exact municipality-code filters and point-to-mesh links are
deterministic. A nearest PLATEAU footprint is only an `ambiguous` candidate: proximity does
not establish official facility/building identity. The evidence reports ambiguous and
unmatched coverage separately for medical and care facilities in each city.

The existing PLATEAU road graph remains `experimental`; it is never relabeled as an official
pedestrian graph. The legacy P04 2020 network medical distance is shown separately from MHLW
2026 straight-line distance and is explicitly non-comparable because the destination source
and metric differ.

## Time and provenance

Every city evidence manifest shows the mixed source timeline rather than coercing it to one
date: census/J-SHIS 2020, Economic Census 2021, P11 2022, NPA 2023/2024 event dates,
PLATEAU 2025, official future trial years 2025/2050/2070, MHLW medical 2026-06-01 and MHLW
care 2026-06-30. No interpolation is performed.

Lineage includes SHA-256 for every canonical/input artifact, raw source hashes carried by
canonical records, algorithm versions, source contributions, missing datasets and claim
boundaries. Data quality remains a set of dimensions—source authority, temporal fitness,
spatial linkage, schema validity and claim boundary—not one quality score.

## Internal artifacts and rebuild

The analysis is not copied to `frontend/public` because it contains internal small-area
context, including pre-privacy-aggregation future values.

- `analysis/outputs/real/open_data/municipal_open_data_analysis.geojson`
- `analysis/outputs/real/open_data/municipal_open_data_findings.json`
- `analysis/outputs/real/open_data/municipal_open_data_evidence.json`
- `analysis/outputs/real/open_data/municipal_open_data_evidence.csv`
- `analysis/outputs/real/open_data/municipal_open_data_evidence.html`
- `analysis/outputs/real/open_data/municipal_open_data_analysis_summary.json`

Rebuild and validate from the repository root:

```bash
python -m analysis.scripts.build_municipal_open_data_analysis
python -m pytest backend/tests/test_real_municipal_open_data_analysis.py
```

The JSON/CSV/print-HTML evidence exporter is deterministic and HTML-escapes source content.
It rejects public export and automatic Investigation/Decision creation.

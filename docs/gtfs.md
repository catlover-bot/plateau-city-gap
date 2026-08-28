# GTFS / GTFS-JP source status

Official-source discovery was repeated on 2026-08-28. The evidence snapshot is
`analysis/outputs/real/gtfs_official_source_audit.json`.

## Result

| City | Capability | Feed ingested | Reason |
|---|---|---:|---|
| Maizuru | unavailable | no | The current 30-dataset BODIK organization catalog and checked municipal/operator pages exposed no downloadable official GTFS/GTFS-JP feed. A plan to promote GTFS is not a feed. |
| Fujisawa | unavailable | no | No stable public feed was found. Kanachu appears as a 2026 ODPT Challenge cooperating operator, but no unrestricted, stable feed was obtained or licensed. |

Primary checked sources include the [Maizuru open-data entry](https://www.city.maizuru.kyoto.jp/shisei/0000004879.html),
[Maizuru bus-location announcement](https://www.city.maizuru.kyoto.jp/kurashi/0000015340.html),
[Fujisawa bus information](https://www.city.fujisawa.kanagawa.jp/tosikei/bus_norikata.html),
[Kanachu](https://www.kanachu.co.jp/), [Enoden Bus](https://www.enoden.co.jp/bus/search/map),
and the [ODPT Challenge 2026 participant list](https://challenge2026.odpt.org/ja/outline.html).

This is a dated discovery result, not proof that a feed can never exist. A pilot owner
must obtain an official feed URL/file, license, permitted retention terms and update
contact. Until then, P11 stop points remain a separate facility source and no service
frequency, operating-hours or weekday/weekend metric is produced.

## Ingestion gate

The adapter accepts only a bounded ZIP with traversal, expansion, encryption and member
checks. It validates `stops`, `routes`, `trips`, `stop_times`, `calendar` and
`calendar_dates`, including referential integrity and after-midnight GTFS times. A
`gtfs_feeds` row is created only after such a real source is registered. P11 cannot pass
this contract and is never transformed into fake GTFS.

When an authorized feed becomes available, service frequency, service span and
weekday/weekend availability may be calculated as separate components. Time-dependent
routing remains outside the current pilot scope unless explicitly validated.

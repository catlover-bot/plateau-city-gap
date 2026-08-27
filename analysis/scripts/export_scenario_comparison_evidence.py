"""Export a print-friendly A/B/C municipal comparison Evidence Package V2."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from analysis.scripts.export_scenario_evidence import OUTPUT, _package

DEFAULT_PLANS = ("network-overall-3", "network-elderly-3", "network-balanced-3")
COLOURS = ("#156b8a", "#b76521", "#567337")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _comparison_package(plan_ids: tuple[str, str, str]) -> dict[str, Any]:
    packages = [_package(plan_id) for plan_id in plan_ids]
    first = packages[0]
    return {
        "schema_version": "2.0.0",
        "package_type": "municipal_scenario_comparison_evidence",
        "generated_at": first["generated_at"],
        "city": first["city"],
        "comparison": [
            {
                "comparison_label": label,
                "scenario": package["scenario"],
                "versions": package["versions"],
                "field_check_items": package["field_check_items"],
                "limitations": package["limitations"],
            }
            for label, package in zip(("A", "B", "C"), packages, strict=True)
        ],
        "source_datasets": first["source_datasets"],
        "constraints": first["constraints"],
        "review_boundary": {
            "recommendation": None,
            "preferred_scenario": None,
            "siting_feasibility": "not_determined",
            "map_role": "candidate location evidence; not a cadastral or legal map",
            "decision": "municipal review and field confirmation required",
        },
    }


def _map_svg(package: dict[str, Any]) -> str:
    sites = [
        (scenario["comparison_label"], site)
        for scenario in package["comparison"]
        for site in scenario["scenario"]["sites"]
    ]
    longitudes = [float(site["longitude"]) for _, site in sites]
    latitudes = [float(site["latitude"]) for _, site in sites]
    west, east = min(longitudes), max(longitudes)
    south, north = min(latitudes), max(latitudes)
    lon_span = max(east - west, 0.001)
    lat_span = max(north - south, 0.001)
    points = []
    for label, site in sites:
        x = 55 + (float(site["longitude"]) - west) / lon_span * 650
        y = 355 - (float(site["latitude"]) - south) / lat_span * 300
        colour = COLOURS[ord(label) - ord("A")]
        points.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{colour}" />'
            f'<text x="{x + 10:.1f}" y="{y + 4:.1f}">{html.escape(label)}-'
            f'{int(site["site_order"])}</text>'
        )
    return f"""<svg viewBox="0 0 760 400" role="img" aria-label="候補地点座標図">
      <rect x="40" y="30" width="690" height="345" fill="#f7f8f5" stroke="#839098" />
      <path d="M40 145H730M40 260H730M270 30V375M500 30V375" stroke="#d7dcdd" />
      {''.join(points)}
      <text x="45" y="395">座標範囲 {west:.5f}–{east:.5f}E / {south:.5f}–{north:.5f}N</text>
    </svg>"""


def _render(package: dict[str, Any]) -> str:
    escape = lambda value: html.escape(str(value))
    comparisons = package["comparison"]
    impact_keys = sorted(
        set.intersection(*(set(item["scenario"]["impact"]) for item in comparisons))
    )
    metric_rows = "".join(
        "<tr><th>"
        + escape(key)
        + "</th>"
        + "".join(f"<td>{escape(item['scenario']['impact'][key])}</td>" for item in comparisons)
        + "</tr>"
        for key in impact_keys
    )
    site_rows = "".join(
        f"<tr><td>{escape(item['comparison_label'])}</td><td>{site['site_order']}</td>"
        f"<td>{escape(site['candidate_id'])}</td><td>{float(site['latitude']):.6f}, "
        f"{float(site['longitude']):.6f}</td><td>{escape(site['planning_context'])}</td>"
        f"<td>{escape(site['hazard_context'])}</td></tr>"
        for item in comparisons
        for site in item["scenario"]["sites"]
    )
    sources = "".join(
        f"<tr><td>{escape(source['dataset_key'])}</td><td>{escape(source['year'])}</td>"
        f"<td>{escape(source['provider'])}</td><td>{escape(source['title'])}</td></tr>"
        for source in package["source_datasets"]
    )
    field_rows = "".join(
        f"<tr><td>{item['comparison_label']}</td><td>{check['site_order']}</td>"
        f"<td>{escape(check['candidate_id'])}</td><td>{escape(check['site_access'])}</td>"
        f"<td>{escape(check['road_safety'])}</td><td>{escape(check['hazard_confirmation'])}</td>"
        f"<td>{escape(check['notes'])}</td></tr>"
        for item in comparisons
        for check in item["field_check_items"]
    )
    limitations = sorted(
        {value for item in comparisons for value in item["limitations"]}
    )
    limitation_items = "".join(f"<li>{escape(value)}</li>" for value in limitations)
    provenance_rows = "".join(
        f"<tr><td>{item['comparison_label']}</td>"
        f"<td>{escape(item['versions']['dataset_version_key'])}</td>"
        f"<td>{escape(item['versions']['network_version'])}</td>"
        f"<td>{escape(item['versions']['algorithm_version'])}</td>"
        f"<td>{escape(item['versions']['scenario_config_hash'])}</td></tr>"
        for item in comparisons
    )
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>CITY GAP Evidence Package V2</title><style>
:root{{font-family:system-ui,sans-serif;color:#17242b;background:#eef1ef}}body{{max-width:1050px;margin:auto;padding:34px}}
header,section{{background:white;border:1px solid #c8d0d2;padding:24px;margin:18px 0}}h1,h2{{color:#173e50}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #d6dcde;padding:7px;text-align:left}}
.boundary{{border-left:7px solid #b05c27;background:#fff5e9;padding:16px}}svg{{width:100%;height:auto}}small{{color:#52616a}}
@media print{{body{{padding:0;background:white}}header,section{{break-inside:avoid;border-color:#777}}}}
</style></head><body>
<header><small>CITY GAP · MUNICIPAL REVIEW</small><h1>Scenario Comparison Evidence Package V2</h1>
<p>{escape(package['city']['name'])} / A・B・C 複数案比較</p><p>Generated: {escape(package['generated_at'])}</p></header>
<p class="boundary">本資料は自動推奨ではありません。優先案・設置可能性は未判定で、自治体レビューと現地確認が必要です。</p>
<section><h2>前提とデータ年</h2><table><tr><th>データ</th><th>年</th><th>提供者</th><th>名称</th></tr>{sources}</table></section>
<section><h2>A/B/C 比較</h2><table><tr><th>指標</th><th>A</th><th>B</th><th>C</th></tr>{metric_rows}</table></section>
<section><h2>候補位置・計画・災害</h2><table><tr><th>案</th><th>順</th><th>候補ID</th><th>座標</th><th>都市計画</th><th>災害</th></tr>{site_rows}</table></section>
<section><h2>候補位置図</h2>{_map_svg(package)}<small>座標プロット。地籍・道路通行可否・法的境界を示す地図ではありません。</small></section>
<section><h2>道路network caveat</h2><p>{escape(package['constraints']['route_semantics'])}</p>
<p>Pedestrian network: {escape(package['constraints']['pedestrian_network'])}</p></section>
<section><h2>現地確認</h2><table><tr><th>案</th><th>順</th><th>候補</th><th>進入</th><th>道路安全</th><th>災害</th><th>notes</th></tr>{field_rows}</table></section>
<section><h2>Provenance / Algorithm</h2><table><tr><th>案</th><th>dataset</th><th>network</th><th>algorithm</th><th>config hash</th></tr>{provenance_rows}</table></section>
<section><h2>Limitations</h2><ul>{limitation_items}</ul></section>
</body></html>"""


def export(plan_ids: tuple[str, str, str], output_directory: Path) -> dict[str, Any]:
    package = _comparison_package(plan_ids)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "comparison.json"
    html_path = output_directory / "print.html"
    json_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    html_path.write_text(_render(package), encoding="utf-8")
    manifest = {
        "schema_version": "2.0.0",
        "plan_ids": list(plan_ids),
        "generated_at": package["generated_at"],
        "recommendation": None,
        "formats": {
            "json": {"bytes": json_path.stat().st_size, "sha256": _sha256(json_path)},
            "html": {"bytes": html_path.stat().st_size, "sha256": _sha256(html_path)},
        },
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-id", action="append", dest="plan_ids")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=OUTPUT / "evidence_packages" / "scenario-comparison-v2",
    )
    args = parser.parse_args()
    plan_ids = tuple(args.plan_ids or DEFAULT_PLANS)
    if len(plan_ids) != 3 or len(set(plan_ids)) != 3:
        parser.error("exactly three distinct --plan-id values are required")
    print(json.dumps(export(plan_ids, args.output_directory), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

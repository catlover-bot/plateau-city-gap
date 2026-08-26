"""Export a municipal review evidence package as JSON, CSV and print-friendly HTML."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from backend.citygap_platform.domain.scenarios import FieldCheck

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "analysis/outputs/real"
SCENARIOS = OUTPUT / "maizuru_network_scenarios.json"
SUMMARY = OUTPUT / "maizuru_summary.json"
INVENTORY = OUTPUT / "maizuru_plateau_inventory.json"
CANONICAL = OUTPUT / "maizuru_scenario_canonical_manifest.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _find_plan(report: dict[str, Any], plan_id: str) -> dict[str, Any]:
    for plans in report["plans"].values():
        for plan in plans.values():
            if plan["plan_id"] == plan_id:
                return plan
    raise ValueError(f"Unknown scenario plan: {plan_id}")


def _package(plan_id: str) -> dict[str, Any]:
    report = _load(SCENARIOS)
    summary = _load(SUMMARY)
    inventory = _load(INVENTORY)
    canonical = _load(CANONICAL)
    plan = _find_plan(report, plan_id)
    scenario = {key: value for key, value in plan.items() if key != "mesh_results"}
    sources = []
    for key, source in summary["datasets"].items():
        sources.append(
            {
                "dataset_key": key,
                "title": source["title"],
                "provider": source.get("provider", "Project PLATEAU"),
                "year": source["year"],
                "source_url": source.get("source_url", source.get("url")),
                "license": source.get("license"),
            }
        )
    field_checks = [
        {
            "site_order": site["site_order"],
            "candidate_id": site["candidate_id"],
            **FieldCheck().as_dict(),
        }
        for site in plan["sites"]
    ]
    return {
        "schema_version": "1.0.0",
        "package_type": "municipal_scenario_evidence",
        "generated_at": report["generated_at"],
        "city": report["city"],
        "scenario": scenario,
        "versions": {
            "dataset_version_key": canonical["dataset_version_key"],
            "dataset_archive_sha256": inventory["archive"]["sha256"],
            "plateau_product_specification_version": inventory["dataset"][
                "product_specification_version"
            ],
            "network_version": report["network"]["graph_version"],
            "context_version": canonical["context_version"],
            "context_config_hash": canonical["context_config_hash"],
            "algorithm_version": report["algorithm_version"],
            "scenario_config_hash": canonical["config_hash"],
        },
        "source_datasets": sources,
        "constraints": {
            "minimum_site_separation_m": report["candidate_set"]["minimum_site_separation_m"],
            "candidate_count": report["candidate_set"]["count"],
            "land_availability_confirmed": report["candidate_set"]["land_availability_confirmed"],
            "pedestrian_network": report["network"]["pedestrian_network"],
            "route_semantics": report["network"]["route_semantics"],
            "context_policy": report["context_policy"],
        },
        "field_check_items": field_checks,
        "limitations": report["limitations"],
        "review_boundary": {
            "recommendation": None,
            "siting_feasibility": "not_determined",
            "hazard_overlap": "additional confirmation; never automatic rejection",
            "field_checks": "human observations; never automatic approval",
        },
    }


def _csv_rows(package: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []

    def add(
        record_type: str,
        key: str,
        value: Any,
        *,
        site_order: int | None = None,
        unit: str = "",
        source_id: str = "",
        note: str = "",
    ) -> None:
        rows.append(
            {
                "record_type": record_type,
                "site_order": "" if site_order is None else site_order,
                "key": key,
                "value": (
                    json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                    if isinstance(value, (dict, list))
                    else value
                ),
                "unit": unit,
                "source_id": source_id,
                "note": note,
            }
        )

    plan = package["scenario"]
    add("scenario", "plan_id", plan["plan_id"])
    add("scenario", "objective", plan["objective"])
    add("scenario", "exactness", plan["exactness"])
    for key, value in plan["impact"].items():
        add("metric", key, value)
    for site in plan["sites"]:
        order = int(site["site_order"])
        for key in (
            "candidate_id",
            "node_id",
            "road_gml_id",
            "road_surface_id",
            "road_name",
            "longitude",
            "latitude",
            "component_id",
            "landuse_context",
            "planning_context",
            "hazard_context",
            "hazard_review_status",
            "siting_feasibility",
        ):
            add("site", key, site[key], site_order=order, source_id=site["road_gml_id"])
        for key, value in site["feasibility_flags"].items():
            add("review_flag", key, value, site_order=order)
    for source in package["source_datasets"]:
        add(
            "source_dataset",
            source["dataset_key"],
            source["title"],
            unit=str(source["year"]),
            source_id=source["source_url"] or "",
            note=source["provider"],
        )
    for check in package["field_check_items"]:
        for key, value in check.items():
            if key not in {"site_order", "candidate_id"}:
                add("field_check", key, value, site_order=int(check["site_order"]))
    return rows


def _render_html(package: dict[str, Any]) -> str:
    plan = package["scenario"]
    escape = lambda value: html.escape(str(value))
    metric_rows = "".join(
        f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>"
        for key, value in plan["impact"].items()
    )
    site_sections = []
    for site, checklist in zip(plan["sites"], package["field_check_items"], strict=True):
        flags = "".join(
            f"<li>{escape(key)}: {escape(value)}</li>"
            for key, value in site["feasibility_flags"].items()
            if key.endswith("_attention")
        )
        checks = "".join(
            f"<tr><th>{escape(key)}</th><td>{escape(value)}</td></tr>"
            for key, value in checklist.items()
            if key not in {"site_order", "candidate_id"}
        )
        site_sections.append(
            f"""
            <section>
              <h3>候補 {escape(site["site_order"])}: {escape(site["candidate_id"])}</h3>
              <dl>
                <dt>PLATEAU道路 gml:id</dt><dd>{escape(site["road_gml_id"])}</dd>
                <dt>道路</dt><dd>{escape(site["road_name"])}</dd>
                <dt>土地利用</dt><dd>{escape(site["landuse_context"])}</dd>
                <dt>都市計画</dt><dd>{escape(site["planning_context"])}</dd>
                <dt>災害文脈</dt><dd>{escape(site["hazard_context"])}</dd>
                <dt>判定</dt><dd>{escape(site["siting_feasibility"])}</dd>
              </dl>
              <h4>Review flags</h4><ul>{flags}</ul>
              <h4>現地確認票</h4><table>{checks}</table>
            </section>
            """
        )
    sources = "".join(
        f"<li>{escape(source['year'])} — {escape(source['provider'])}: "
        f"{escape(source['title'])}</li>"
        for source in package["source_datasets"]
    )
    limitations = "".join(f"<li>{escape(value)}</li>" for value in package["limitations"])
    rendered = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CITY GAP Evidence — {escape(plan["plan_id"])}</title>
  <style>
    :root {{ color: #172026; background: #f4f2ec; font-family: system-ui, sans-serif; }}
    body {{ max-width: 960px; margin: 0 auto; padding: 32px; }}
    header {{ border-bottom: 4px solid #24485c; padding-bottom: 16px; }}
    h1, h2, h3, h4 {{ color: #17394a; }}
    section {{ background: #fff; border: 1px solid #c9ced0; margin: 20px 0; padding: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #d9dddf; padding: 7px; text-align: left; vertical-align: top; }}
    th {{ width: 42%; }}
    dt {{ font-weight: 700; margin-top: 8px; }}
    dd {{ margin-left: 0; }}
    .boundary {{ border-left: 6px solid #a45c2a; padding: 12px 16px; background: #fff8ed; }}
    @media print {{ body {{ padding: 0; background: #fff; }} section {{ break-inside: avoid; }} }}
  </style>
</head>
<body>
  <header>
    <p>CITY GAP Municipal Review Evidence</p>
    <h1>{escape(plan["label"])} — {escape(plan["site_count"])}地点</h1>
    <p>{escape(plan["objective"])}</p>
    <p>{escape(plan["exactness"])}</p>
  </header>
  <p class="boundary">自動推奨ではありません。設置可能性は未判定です。災害重複は追加確認事項です。</p>
  <section><h2>影響指標</h2><table>{metric_rows}</table></section>
  {"".join(site_sections)}
  <section><h2>出典データ</h2><ul>{sources}</ul></section>
  <section><h2>制約・限界</h2><ul>{limitations}</ul></section>
  <footer><p>Algorithm: {escape(package["versions"]["algorithm_version"])} / Network: {escape(package["versions"]["network_version"])}</p></footer>
</body>
</html>
"""
    return "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"


def export(plan_id: str, output_directory: Path) -> dict[str, Any]:
    package = _package(plan_id)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "evidence.json"
    csv_path = output_directory / "evidence.csv"
    html_path = output_directory / "print.html"
    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = _csv_rows(package)
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    html_path.write_text(_render_html(package), encoding="utf-8")
    artifacts = {
        name: {
            "path": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for name, path in (("json", json_path), ("csv", csv_path), ("html", html_path))
    }
    manifest = {
        "schema_version": "1.0.0",
        "plan_id": plan_id,
        "generated_at": package["generated_at"],
        "formats": artifacts,
        "database_executed": False,
    }
    (output_directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-id", default="network-overall-3")
    parser.add_argument("--output-directory", type=Path)
    arguments = parser.parse_args()
    destination = arguments.output_directory or (OUTPUT / "evidence_packages" / arguments.plan_id)
    print(json.dumps(export(arguments.plan_id, destination), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

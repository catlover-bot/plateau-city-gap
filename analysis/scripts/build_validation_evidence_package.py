"""Build the public-safe Validation Evidence Package and reproducibility bundle."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from backend.citygap_platform.domain.validation import (
    CLAIM_REGISTRY,
    EVIDENCE_DIMENSIONS,
    UNCERTAINTY_CATEGORIES,
)

ROOT = Path(__file__).resolve().parents[2]
VALIDATION = ROOT / "analysis/outputs/real/validation"
PUBLIC = ROOT / "frontend/public/data/validation"
PACKAGE = VALIDATION / "evidence_package"
REPRODUCIBILITY = ROOT / "analysis/outputs/real/validation/reproducibility"


def _load(name: str) -> dict[str, Any]:
    return json.loads((VALIDATION / name).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _evidence_strength(claim_key: str) -> dict[str, str]:
    values = {dimension: "NO" for dimension in EVIDENCE_DIMENSIONS}
    values.update(source_verified="YES", reproducible="YES")
    if claim_key in {"experimental_network_accessibility", "shelter_reachability"}:
        values.update(independent_verifier="YES", reference_model_agreement="YES")
    else:
        values.update(independent_verifier="NOT_AVAILABLE", reference_model_agreement="NOT_AVAILABLE")
    if claim_key in {
        "hazard_stress_test", "network_criticality", "future_population_allocation",
        "scenario_improvement", "experimental_network_accessibility",
    }:
        values["assumption_sensitive"] = "YES"
    values["municipal_review"] = "NO"
    values["field_verified"] = "NO"
    return values


def _uncertainty_ledger() -> list[dict[str, Any]]:
    descriptions = {
        "data_coverage": "Official PLATEAU network output and municipal road ledgers were not available for direct comparison.",
        "temporal_mismatch": "Product cities have one available official PLATEAU version; temporal validation uses Kunitachi as a validation-only city.",
        "model_approximation": "Road-surface adjacency and building representative points simplify entrances and crossing behavior.",
        "network_semantics": "Neither the experimental graph nor OSM reference is a field-observed pedestrian ground truth.",
        "facility_availability": "Published facility points do not prove hours, capacity, entrance, or event-time availability.",
        "scenario_assumption": "Stress and intervention results are counterfactual outputs under named fixed rules.",
        "population_allocation": "Mesh totals are deterministically estimated across qualifying buildings, not observed per-building residents.",
        "optimization_approximation": "Candidate search operates within declared candidate sets and is not a policy optimum.",
    }
    return [
        {
            "category": category,
            "known_limitation": descriptions[category],
            "confidence_percentage": None,
            "municipal_review": "not_reviewed",
            "field_validation": "awaiting_field_validation",
        }
        for category in UNCERTAINTY_CATEGORIES
    ]


def build() -> dict[str, Any]:
    network = _load("network_cross_validation.json")
    sensitivity = _load("sensitivity_validation.json")
    temporal = _load("kunitachi_real_temporal_validation.json")
    rehearsal = _load("municipal_pilot_rehearsal.json")
    temporal_themes = list(temporal["themes"].values()) if isinstance(temporal["themes"], dict) else temporal["themes"]
    claims = [
        {
            "claim": claim.claim_key,
            "primary_model": claim.what_it_means,
            "claim_boundary": claim.what_it_does_not_mean,
            "validation_method": list(claim.validation_method),
            "required_data": list(claim.required_data),
            "validation_status": claim.current_validation_status.value,
            "evidence_strength": _evidence_strength(claim.claim_key),
            "municipal_feedback": "not_reviewed",
            "field_validation": "awaiting_field_validation",
        }
        for claim in CLAIM_REGISTRY
    ]
    package = {
        "schema_version": "citygap-validation-evidence-v1.0.0",
        "generated_from": network["generated_at"],
        "ground_truth_claimed": False,
        "municipal_approval_claimed": False,
        "confidence_percentage_used": False,
        "claims": claims,
        "network_validation": {
            "claim": network["claim"],
            "primary_model": "experimental PLATEAU LOD1 road-surface adjacency graph",
            "reference_model": "OpenStreetMap ODbL pinned Overpass extract",
            "sample_design": network["validation_method"],
            "metrics": {city["city_id"]: city["metrics"] for city in network["cities"]},
            "disagreement_examples": {
                city["city_id"]: city["major_disagreements"] for city in network["cities"]
            },
            "coverage": {city["city_id"]: city["coverage"] for city in network["cities"]},
            "known_limitations": network["reference_warning"],
            "validation_status": network["validation_status"],
            "provenance": {
                city["city_id"]: {
                    "primary": city["primary_network"],
                    "reference": city["reference_network"],
                    "algorithm_version": city["algorithm_version"],
                }
                for city in network["cities"]
            },
        },
        "assumption_sensitivity": sensitivity,
        "temporal_real_data_validation": {**temporal, "themes": temporal_themes},
        "uncertainty_ledger": _uncertainty_ledger(),
        "pilot_rehearsal": rehearsal,
    }
    package["expected_summary_sha256"] = _canonical_sha256({
        "network": package["network_validation"]["metrics"],
        "temporal": [theme["diff_counts"] for theme in temporal_themes],
        "pilot": rehearsal["counts"],
    })
    return package


def _write_csv(path: Path, package: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow([
            "record_type", "scope", "key", "value", "validation_status",
            *EVIDENCE_DIMENSIONS, "claim_boundary",
        ])
        for claim in package["claims"]:
            writer.writerow([
                "claim", "all", claim["claim"], claim["primary_model"],
                claim["validation_status"],
                *(claim["evidence_strength"][dimension] for dimension in EVIDENCE_DIMENSIONS),
                claim["claim_boundary"],
            ])
        network = package["network_validation"]
        blanks = [""] * len(EVIDENCE_DIMENSIONS)
        for city, metrics in network["metrics"].items():
            for key, value in metrics.items():
                writer.writerow(["network_metric", city, key, json.dumps(value), network["validation_status"], *blanks, network["known_limitations"]])
            writer.writerow(["coverage", city, "network_coverage", json.dumps(network["coverage"][city], ensure_ascii=False), network["validation_status"], *blanks, network["known_limitations"]])
            writer.writerow(["provenance", city, "network_provenance", json.dumps(network["provenance"][city], ensure_ascii=False), network["validation_status"], *blanks, network["known_limitations"]])
            for disagreement in network["disagreement_examples"][city]:
                writer.writerow(["disagreement", city, disagreement["sample_id"], json.dumps(disagreement, ensure_ascii=False), network["validation_status"], *blanks, "cause candidate requires review"])
        for city, result in package["assumption_sensitivity"]["cities"].items():
            for row in result["hazard_assumption_matrix"]:
                writer.writerow(["assumption_sensitivity", city, f"{row['hazard_type']}:{row['assumption']}", json.dumps(row, ensure_ascii=False), result["validation_status"], *blanks, "counterfactual rule; not probability"])


def _write_html(path: Path, package: dict[str, Any]) -> None:
    city_rows = "".join(
        f"<tr><th>{html.escape(city)}</th><td>{value['sample_count']}</td>"
        f"<td>{value['distance_mae_m']:.1f} m</td><td>{value['connectivity_agreement_fraction']:.1%}</td>"
        f"<td>{value['spearman_rank_correlation']:.3f}</td></tr>"
        for city, value in package["network_validation"]["metrics"].items()
    )
    claim_rows = "".join(
        f"<tr><th>{html.escape(claim['claim'])}</th><td>{html.escape(claim['validation_status'])}</td>"
        + "".join(f"<td>{claim['evidence_strength'][dimension]}</td>" for dimension in EVIDENCE_DIMENSIONS)
        + "</tr>" for claim in package["claims"]
    )
    disagreement_rows = "".join(
        f"<tr><th>{html.escape(city)}</th><td>{html.escape(row['sample_id'])}</td><td>{html.escape(row['reference_agreement'])}</td><td>{html.escape(row['cause_candidate'])}</td></tr>"
        for city, rows in package["network_validation"]["disagreement_examples"].items()
        for row in rows[:5]
    )
    sensitivity_rows = "".join(
        f"<tr><th>{html.escape(city)}</th><td>{len(result['hazard_assumption_matrix'])}</td><td>{len(result['criticality_sensitivity']['models'])}</td><td>{html.escape(result['validation_status'])}</td></tr>"
        for city, result in package["assumption_sensitivity"]["cities"].items()
    )
    temporal_rows = "".join(
        f"<tr><th>{html.escape(theme['theme_label'])}</th><td>{theme['diff_counts']['added']}</td><td>{theme['diff_counts']['removed']}</td><td>{theme['diff_counts']['geometry_changed']}</td><td>{theme['diff_counts']['attribute_changed']}</td></tr>"
        for theme in package["temporal_real_data_validation"]["themes"]
    )
    path.write_text(f"""<!doctype html><html lang="ja"><meta charset="utf-8"><title>CITY GAP Validation Evidence</title>
<style>body{{font:12px/1.55 system-ui;color:#24322b;margin:32px}}h1{{font-family:serif}}table{{border-collapse:collapse;width:100%;margin:16px 0}}th,td{{border:1px solid #abb6ae;padding:6px;text-align:left}}thead{{background:#e7ede8}}.boundary{{border-left:4px solid #99743b;background:#f3eee3;padding:10px}}@media print{{body{{margin:12mm}}section{{break-inside:avoid}}}}</style>
<h1>CITY GAP Validation Evidence Package</h1><p class="boundary">Reference model is not ground truth. No confidence percentage, field approval, or municipal approval is claimed.</p>
<section><h2>Network cross-validation</h2><table><thead><tr><th>City</th><th>Sample</th><th>MAE</th><th>Connectivity agreement</th><th>Spearman</th></tr></thead><tbody>{city_rows}</tbody></table></section>
<section><h2>Disagreement examples</h2><table><thead><tr><th>City</th><th>Sample</th><th>Class</th><th>Cause candidate</th></tr></thead><tbody>{disagreement_rows}</tbody></table></section>
<section><h2>Assumption sensitivity</h2><table><thead><tr><th>City</th><th>Hazard rule runs</th><th>Criticality models</th><th>Status</th></tr></thead><tbody>{sensitivity_rows}</tbody></table></section>
<section><h2>Real temporal diff</h2><table><thead><tr><th>Theme</th><th>Added</th><th>Removed</th><th>Geometry</th><th>Attribute</th></tr></thead><tbody>{temporal_rows}</tbody></table></section>
<section><h2>Evidence strength matrix</h2><table><thead><tr><th>Claim</th><th>Status</th>{''.join(f'<th>{html.escape(x)}</th>' for x in EVIDENCE_DIMENSIONS)}</tr></thead><tbody>{claim_rows}</tbody></table></section>
<section><h2>Uncertainty ledger</h2>{''.join(f"<h3>{html.escape(x['category'])}</h3><p>{html.escape(x['known_limitation'])}</p>" for x in package['uncertainty_ledger'])}</section>
<footer>Summary SHA-256: <code>{package['expected_summary_sha256']}</code></footer></html>""", encoding="utf-8")


def _write_reproducibility(package: dict[str, Any], artifacts: list[Path]) -> None:
    REPRODUCIBILITY.mkdir(parents=True, exist_ok=True)
    raw_sources = [
        {
            "path": "data/raw/osm_reference/maizuru-20260827-overpass.json",
            "sha256": "1308277a253ca2cc4fb7b8d5883a78b7430be66a385210307092f0ee6401d71e",
            "source": "Overpass API historical date query",
            "retrieval_date": "2026-08-27",
            "license": "ODbL",
        },
        {
            "path": "data/raw/osm_reference/fujisawa-20260827-overpass.json",
            "sha256": "1e5b637e583ca340cc1d29d5a382b4f594b5e42b68db7b6ddf873cd94031f9e2",
            "source": "Overpass API historical date query",
            "retrieval_date": "2026-08-27",
            "license": "ODbL",
        },
        {
            "path": "data/raw/temporal_validation/13215_kunitachi_2023_citygml.zip",
            "sha256": "6d437f8808a136cf278ee230e306120ede5674da105040273ca24408f6890e59",
            "source": "https://www.geospatial.jp/ckan/dataset/plateau-13215-kunitachi-shi-2023",
            "retrieval_date": "2026-08-27",
            "license": "PLATEAU catalog terms",
        },
        {
            "path": "data/raw/temporal_validation/13215_kunitachi_2025_citygml.zip",
            "sha256": "bfd34c91a642518d3a8fe7b34f4da23a0c660cfe2bb3968d4f74db28d0c43a51",
            "source": "https://www.geospatial.jp/ckan/dataset/plateau-13215-kunitachi-shi-2025",
            "retrieval_date": "2026-08-27",
            "license": "PLATEAU catalog terms",
        },
    ]
    sensitivity_version = package["assumption_sensitivity"]["algorithm_version"]
    manifest = {
        "schema_version": "citygap-validation-reproducibility-v1.0.0",
        "environment": {"python": ">=3.10", "definition": "pyproject.toml", "lock_note": "install with pip install -e ."},
        "source_manifest": [
            {**source, "included": False, "reason": "large raw source is excluded"}
            for source in raw_sources
        ],
        "commands": {
            "maizuru": "citygap validate reproduce --city maizuru",
            "fujisawa": "citygap validate reproduce --city fujisawa",
            "all": "python -m analysis.scripts.build_validation_evidence_package",
        },
        "algorithm_versions": {
            "network": "network-cross-validation-v1.0.0",
            "sensitivity": sensitivity_version,
            "temporal": package["temporal_real_data_validation"]["algorithm_version"],
        },
        "expected_summary_sha256": package["expected_summary_sha256"],
        "expected_city_metric_sha256": {
            city: _canonical_sha256(metrics)
            for city, metrics in package["network_validation"]["metrics"].items()
        },
        "artifacts": [{"path": str(path.relative_to(ROOT)), "sha256": _sha256(path), "bytes": path.stat().st_size} for path in artifacts],
        "raw_data_included": False,
        "sensitivity_algorithm_version": sensitivity_version,
    }
    (REPRODUCIBILITY / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (REPRODUCIBILITY / "README.md").write_text("""# CITY GAP validation reproducibility bundle

This bundle contains commands, hashes, algorithm versions, and expected summaries. Large raw OSM and PLATEAU CityGML archives are deliberately not tracked. Place checksum-matching files at the manifest paths, install `.[platform,dev]`, then run `citygap validate reproduce --city maizuru` or `--city fujisawa`.

The command verifies pinned source hashes before analysis and compares the resulting city summary with the tracked expected result. OSM and official datasets are reference sources, not field ground truth.
""", encoding="utf-8")


def main() -> None:
    package = build()
    PACKAGE.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    json_path = PACKAGE / "validation_evidence.json"
    csv_path = PACKAGE / "validation_evidence.csv"
    html_path = PACKAGE / "validation_evidence.html"
    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(csv_path, package)
    _write_html(html_path, package)
    artifacts = [json_path, csv_path, html_path]
    manifest = {
        "schema_version": "citygap-validation-package-manifest-v1.0.0",
        "summary_sha256": package["expected_summary_sha256"],
        "artifacts": [{"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size} for path in artifacts],
    }
    manifest_path = PACKAGE / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for path in [*artifacts, manifest_path]:
        (PUBLIC / path.name).write_bytes(path.read_bytes())
    _write_reproducibility(package, [*artifacts, manifest_path])
    print(json.dumps({"package": str(PACKAGE), "summary_sha256": package["expected_summary_sha256"], "artifacts": manifest["artifacts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

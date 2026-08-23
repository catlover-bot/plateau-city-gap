"""Independently recompute every published Decision Studio intervention plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
METRICS = ROOT / "analysis/outputs/real/maizuru_mesh_metrics.csv"
ROBUSTNESS = ROOT / "analysis/outputs/real/maizuru_robustness.json"
INTERVENTIONS = ROOT / "frontend/public/data/intervention_scenarios.json"
EVIDENCE = ROOT / "frontend/public/data/evidence.json"
OUTPUT = ROOT / "analysis/outputs/real/maizuru_decision_studio_verification.json"


def _recompute(
    metrics: pd.DataFrame,
    sites: list[dict[str, Any]],
    worst_decile: np.ndarray,
    robust_indices: np.ndarray,
) -> dict[str, Any]:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
    mesh_x, mesh_y = transformer.transform(metrics["centroid_lon"], metrics["centroid_lat"])
    site_x, site_y = transformer.transform(
        [site["longitude"] for site in sites],
        [site["latitude"] for site in sites],
    )
    distances = np.vstack(
        [
            np.hypot(np.asarray(mesh_x) - x, np.asarray(mesh_y) - y)
            for x, y in zip(site_x, site_y)
        ]
    )
    closest = distances.argmin(axis=0)
    virtual_distance = distances[closest, np.arange(len(metrics))]
    before = metrics["nearest_public_transport_distance_m"].to_numpy(float)
    after = np.minimum(before, virtual_distance)
    reduction = np.maximum(0.0, before - after)
    improved = reduction > 1e-6
    after_percentile = pd.Series(after).rank(method="average", pct=True).to_numpy(float)
    before_score = metrics["exploratory_score_c"].to_numpy(float)
    after_score = (
        metrics["elderly_population_percentile"].to_numpy(float)
        * after_percentile
        * metrics["medical_distance_percentile"].to_numpy(float)
    )
    score_reduction = before_score - after_score
    elderly = metrics["elderly_population"].to_numpy(float)
    worst_reduction = reduction[worst_decile]
    robust_reduction = reduction[robust_indices]
    return {
        "impact": {
            "total_score_c_reduction": round(float(score_reduction.sum()), 9),
            "improved_mesh_count": int(improved.sum()),
            "affected_elderly_population": int(elderly[improved].sum()),
            "mean_improvement_among_improved_m": round(float(reduction[improved].mean()), 9),
            "total_transport_distance_reduction_m": round(float(reduction.sum()), 9),
            "worst_decile_mean_reduction_m": round(float(worst_reduction.mean()), 9),
            "worst_decile_improved_count": int((worst_reduction > 1e-6).sum()),
            "robust_top20_improved_count": int((robust_reduction > 1e-6).sum()),
            "robust_top20_median_reduction_m": round(float(np.median(robust_reduction)), 9),
        },
        "after_distance": after,
        "after_score": after_score,
    }


def verify() -> dict[str, Any]:
    metrics = pd.read_csv(METRICS, dtype={"mesh_code": str})
    metrics = metrics.loc[metrics["rank_c_unfiltered"].notna()].copy().reset_index(drop=True)
    robustness = json.loads(ROBUSTNESS.read_text(encoding="utf-8"))
    interventions = json.loads(INTERVENTIONS.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))

    primary_indices = np.flatnonzero(metrics["primary_eligible"].astype(bool).to_numpy())
    primary_distance = metrics.loc[
        primary_indices, "nearest_public_transport_distance_m"
    ].to_numpy(float)
    worst_count = max(1, int(np.ceil(len(primary_indices) * 0.1)))
    worst_decile = primary_indices[np.argsort(-primary_distance, kind="mergesort")[:worst_count]]
    robust_codes = [row["mesh_code"] for row in robustness["top_candidates"][:20]]
    robust_indices = np.asarray(
        [metrics.index[metrics["mesh_code"].eq(code)][0] for code in robust_codes], dtype=int
    )

    checks = []
    for mode, mode_plans in interventions["plans"].items():
        previous_sites: list[str] = []
        for count, plan in sorted(mode_plans.items(), key=lambda item: int(item[0])):
            recomputed = _recompute(metrics, plan["sites"], worst_decile, robust_indices)
            impact_differences = {
                key: (
                    0.0
                    if isinstance(value, int)
                    and value == plan["impact"][key]
                    else abs(float(value) - float(plan["impact"][key]))
                )
                for key, value in recomputed["impact"].items()
            }
            impact_match = all(difference <= 5e-7 for difference in impact_differences.values())
            mesh_match = all(
                abs(
                    recomputed["after_distance"][index]
                    - plan["mesh_results"][str(row["mesh_code"])]["after_distance_m"]
                )
                <= 0.00051
                and abs(
                    recomputed["after_score"][index]
                    - plan["mesh_results"][str(row["mesh_code"])]["after_score_c"]
                )
                <= 5.1e-10
                for index, row in metrics.iterrows()
            )
            site_ids = [site["candidate_id"] for site in plan["sites"]]
            nested = site_ids[: len(previous_sites)] == previous_sites
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:6674", always_xy=True)
            site_x, site_y = transformer.transform(
                [site["longitude"] for site in plan["sites"]],
                [site["latitude"] for site in plan["sites"]],
            )
            spacing_ok = all(
                np.hypot(
                    site_x[left] - site_x[right],
                    site_y[left] - site_y[right],
                )
                >= 1_500 - 1e-3
                for left in range(len(plan["sites"]))
                for right in range(left)
            )
            evidence_plan = evidence["intervention"]["plans"][mode][count]
            evidence_match = (
                evidence_plan["sites"] == plan["sites"]
                and evidence_plan["impact"] == plan["impact"]
            )
            checks.append(
                {
                    "plan_id": plan["plan_id"],
                    "impact_match_within_5e-7": impact_match,
                    "maximum_impact_difference": max(impact_differences.values()),
                    "mesh_values_match_published_rounding": mesh_match,
                    "greedy_prefix_is_nested": nested,
                    "site_spacing_check": spacing_ok,
                    "evidence_chain_match": evidence_match,
                }
            )
            previous_sites = site_ids
    boolean_checks = (
        "impact_match_within_5e-7",
        "mesh_values_match_published_rounding",
        "greedy_prefix_is_nested",
        "site_spacing_check",
        "evidence_chain_match",
    )
    exact_match = all(all(check[key] for key in boolean_checks) for check in checks)
    return {
        "schema_version": "1.0.0",
        "method": (
            "independent pandas percentile and coordinate-distance recomputation; impacts must match "
            "within 5e-7 and every mesh value must match its published rounding"
        ),
        "plans_checked": len(checks),
        "checks": checks,
        "exact_match": exact_match,
    }


def main() -> None:
    report = verify()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["exact_match"]:
        raise SystemExit("Decision Studio verification failed")


if __name__ == "__main__":
    main()

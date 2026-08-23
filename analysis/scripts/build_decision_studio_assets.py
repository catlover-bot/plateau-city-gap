"""Build reproducible robustness and multi-site Decision Studio assets."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

from analysis.scripts.build_final_demo_assets import (
    ANALYSIS_CRS,
    BORDER,
    BUS_STOPS,
    CITYGML_ZIP,
    METRICS_CSV,
    MIN_CANDIDATE_SEPARATION_M,
    MIN_EXISTING_TRANSPORT_DISTANCE_M,
    STATIONS,
    WEB_CRS,
    _area_label,
    _parse_roads,
    _transport_points,
)
from analysis.scripts.run_final_audit import (
    DEFAULT_REVIEW,
    _comparison_masks,
    _confirmed_review,
    _facility_audit,
)
from analysis.src.city_config import load_city_config
from analysis.src.decision_studio import (
    deterministic_order,
    evaluate_intervention,
    greedy_select,
    pareto_mask,
    percentile_rank,
    robustness_rows,
)
from analysis.src.spatial import boundary_from_plateau, intersects_boundary

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "analysis/config/maizuru.yaml"
FINAL_AUDIT = ROOT / "analysis/outputs/real/final_audit.json"
ROBUSTNESS_OUTPUT = ROOT / "analysis/outputs/real/maizuru_robustness.json"
ROBUST_CSV = ROOT / "analysis/outputs/real/maizuru_robust_candidates.csv"
INTERVENTION_OUTPUTS = {
    1: ROOT / "analysis/outputs/real/maizuru_intervention_1site.json",
    2: ROOT / "analysis/outputs/real/maizuru_intervention_2site.json",
    3: ROOT / "analysis/outputs/real/maizuru_intervention_3site.json",
}
FAIRNESS_OUTPUT = ROOT / "analysis/outputs/real/maizuru_intervention_fairness.json"
ROBUST_OUTPUT = ROOT / "analysis/outputs/real/maizuru_intervention_robust.json"
WEB_ROBUSTNESS = ROOT / "frontend/public/data/robustness.json"
WEB_INTERVENTIONS = ROOT / "frontend/public/data/intervention_scenarios.json"
WEB_EVIDENCE = ROOT / "frontend/public/data/evidence.json"
WEB_MANIFEST = ROOT / "frontend/public/data/manifest.json"


def _write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {"ensure_ascii": False}
    if compact:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = 2
    path.write_text(json.dumps(value, **kwargs) + "\n", encoding="utf-8")


def _generated_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    value = datetime.fromtimestamp(int(epoch), tz=timezone.utc) if epoch else datetime.now(timezone.utc)
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scenario(
    scenario_id: str,
    label: str,
    definition: str,
    metrics: pd.DataFrame,
    score: np.ndarray,
    eligible: np.ndarray,
    components: np.ndarray,
) -> dict[str, Any]:
    order = deterministic_order(metrics["mesh_code"], score, eligible)
    codes = metrics["mesh_code"].astype(str).tolist()
    ranks = {codes[index]: rank for rank, index in enumerate(order, start=1)}
    frontier = pareto_mask(components, eligible)
    return {
        "id": scenario_id,
        "label": label,
        "definition": definition,
        "eligible_count": int(np.asarray(eligible, dtype=bool).sum()),
        "ranks": ranks,
        "top10": {codes[index] for index in order[:10]},
        "top20": {codes[index] for index in order[:20]},
        "pareto": {codes[index] for index in np.flatnonzero(frontier)},
    }


def _build_robustness(metrics: gpd.GeoDataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = load_city_config(CONFIG)
    comparison, primary = _comparison_masks(metrics, config)
    comparison_array = comparison.to_numpy(bool)
    primary_array = primary.to_numpy(bool)
    elderly_pct = metrics["elderly_population_percentile"].to_numpy(float)
    ratio_pct = metrics["elderly_ratio_percentile"].to_numpy(float)
    transport_pct = metrics["transport_distance_percentile"].to_numpy(float)
    medical_pct = metrics["medical_distance_percentile"].to_numpy(float)
    elderly = metrics["elderly_population"].to_numpy(float)
    ratio = metrics["elderly_ratio"].to_numpy(float)
    transport = metrics["nearest_public_transport_distance_m"].to_numpy(float)
    medical = metrics["nearest_medical_distance_m"].to_numpy(float)

    confirmed, _ = _confirmed_review(DEFAULT_REVIEW)
    _, facility = _facility_audit(metrics, config, confirmed.get("maizuru", []))
    filtered_medical = facility["filtered_medical_distance"].to_numpy(float)
    filtered_pct = np.full(len(metrics), np.nan)
    filtered_pct[comparison_array] = percentile_rank(filtered_medical[comparison_array])
    buffer_transport = facility["buffer_transport_distance"].to_numpy(float)
    buffer_medical = facility["buffer_filtered_medical_distance"].to_numpy(float)
    buffer_transport_pct = np.full(len(metrics), np.nan)
    buffer_medical_pct = np.full(len(metrics), np.nan)
    buffer_transport_pct[comparison_array] = percentile_rank(buffer_transport[comparison_array])
    buffer_medical_pct[comparison_array] = percentile_rank(buffer_medical[comparison_array])

    no_threshold = comparison_array
    high_threshold = comparison_array & metrics["population"].ge(50).to_numpy() & metrics[
        "elderly_population"
    ].ge(20).to_numpy()
    scenarios = [
        _scenario(
            "S1",
            "高齢者数 × 交通 × 医療",
            "Primary Score C。人口20人以上・65歳以上10人以上。",
            metrics,
            elderly_pct * transport_pct * medical_pct,
            primary_array,
            np.column_stack([elderly, transport, medical]),
        ),
        _scenario(
            "S2",
            "高齢化率 × 交通 × 医療",
            "needを65歳以上人口ではなく高齢化率とする。",
            metrics,
            ratio_pct * transport_pct * medical_pct,
            primary_array,
            np.column_stack([ratio, transport, medical]),
        ),
        _scenario(
            "S3",
            "高齢者数 × 交通",
            "医療距離を積から外す。",
            metrics,
            elderly_pct * transport_pct,
            primary_array,
            np.column_stack([elderly, transport]),
        ),
        _scenario(
            "S4",
            "高齢者数 × 医療",
            "交通距離を積から外す。",
            metrics,
            elderly_pct * medical_pct,
            primary_array,
            np.column_stack([elderly, medical]),
        ),
        _scenario(
            "S5",
            "一般利用不明の医療を除外",
            "uncertain_access医療を除外し、医療percentileを再計算。",
            metrics,
            elderly_pct * transport_pct * filtered_pct,
            primary_array,
            np.column_stack([elderly, transport, filtered_medical]),
        ),
        _scenario(
            "S6",
            "市境外2km + 医療利用可否",
            "同一府P11/P04を市境外2kmまで含め、uncertain_accessを除外。",
            metrics,
            elderly_pct * buffer_transport_pct * buffer_medical_pct,
            primary_array,
            np.column_stack([elderly, buffer_transport, buffer_medical]),
        ),
        _scenario(
            "S7a",
            "人口閾値なし",
            "秘匿・合算影響のない比較対象に人口閾値を適用しない。",
            metrics,
            elderly_pct * transport_pct * medical_pct,
            no_threshold,
            np.column_stack([elderly, transport, medical]),
        ),
        _scenario(
            "S7b",
            "人口50 / 65歳以上20",
            "Primaryより厳しい人口閾値を適用。",
            metrics,
            elderly_pct * transport_pct * medical_pct,
            high_threshold,
            np.column_stack([elderly, transport, medical]),
        ),
        _scenario(
            "S8",
            "Pareto候補のみ",
            "高齢者数・交通・医療の全要素で劣後しないPrimary候補をScore C順に表示。",
            metrics,
            elderly_pct * transport_pct * medical_pct,
            primary_array
            & pareto_mask(np.column_stack([elderly, transport, medical]), primary_array),
            np.column_stack([elderly, transport, medical]),
        ),
    ]
    rows = robustness_rows(metrics, scenarios)
    report_scenarios = [
        {
            "id": item["id"],
            "label": item["label"],
            "definition": item["definition"],
            "eligible_count": item["eligible_count"],
        }
        for item in scenarios
    ]
    report = {
        "schema_version": "1.0.0",
        "generated_at": _generated_at(),
        "scenario_count": len(scenarios),
        "interpretation": "頻度は設定した分析条件内の出現回数であり、確率・信頼度ではない。",
        "ranking_rule": (
            "Top 10出現回数の降順、median rankの昇順、Top 20出現回数の降順、"
            "mesh code昇順。新しい合成スコアは作らない。"
        ),
        "scenarios": report_scenarios,
        "candidates": rows,
        "top_candidates": rows[:20],
    }
    return report, rows


def _candidate_pool() -> tuple[pd.DataFrame, dict[str, Any]]:
    boundary = boundary_from_plateau(gpd.read_file(BORDER))
    with zipfile.ZipFile(CITYGML_ZIP) as archive:
        roads, inventory = _parse_roads(archive)
    city_roads = intersects_boundary(roads, boundary).reset_index(drop=True)
    transformer = Transformer.from_crs(WEB_CRS, ANALYSIS_CRS, always_xy=True)
    x, y = transformer.transform(city_roads["anchor_lon"], city_roads["anchor_lat"])
    points = gpd.GeoDataFrame(
        city_roads.drop(columns="geometry"),
        geometry=gpd.points_from_xy(x, y),
        crs=ANALYSIS_CRS,
    )
    transport = _transport_points(boundary).to_crs(ANALYSIS_CRS)
    nearest = gpd.sjoin_nearest(points, transport, how="left", distance_col="existing_transport_distance_m")
    nearest = nearest.loc[~nearest.index.duplicated(keep="first")]
    pool = nearest.loc[
        nearest["existing_transport_distance_m"] > MIN_EXISTING_TRANSPORT_DISTANCE_M
    ].reset_index(drop=True)
    pool["candidate_x"] = pool.geometry.x
    pool["candidate_y"] = pool.geometry.y
    return pd.DataFrame(pool.drop(columns="geometry")), inventory


def _serialize_plan(
    mode: str,
    site_count: int,
    selected: list[int],
    result: dict[str, Any],
    pool: pd.DataFrame,
    metrics: pd.DataFrame,
) -> dict[str, Any]:
    sites = []
    for position, index in enumerate(selected):
        row = pool.iloc[index]
        sites.append(
            {
                "site_order": position + 1,
                "candidate_id": str(row["road_id"]),
                "longitude": float(row["anchor_lon"]),
                "latitude": float(row["anchor_lat"]),
                "road_name": None if pd.isna(row["road_name"]) else str(row["road_name"]),
                "nearest_existing_transport_name": str(row["transport_name"]),
                "existing_transport_distance_m": round(float(row["existing_transport_distance_m"]), 3),
            }
        )
    mesh_results: dict[str, Any] = {}
    for index, row in metrics.iterrows():
        improved = bool(result["improved"][index])
        site_position = int(result["closest_site_position"][index]) if improved else -1
        mesh_results[str(row["mesh_code"])] = {
            "before_distance_m": round(float(row["nearest_public_transport_distance_m"]), 3),
            "after_distance_m": round(float(result["after_distance"][index]), 3),
            "distance_reduction_m": round(float(result["distance_reduction"][index]), 3),
            "before_score_c": round(float(row["exploratory_score_c"]), 9),
            "after_score_c": round(float(result["after_score"][index]), 9),
            "score_c_reduction": round(float(result["score_reduction"][index]), 9),
            "assigned_site_id": sites[site_position]["candidate_id"] if site_position >= 0 else None,
        }
    values = result["objective_values"]
    impact = {
        key: round(float(value), 9) if isinstance(value, float) else int(value)
        for key, value in values.items()
    }
    top_indices = np.argsort(-result["score_reduction"], kind="mergesort")[:10]
    return {
        "plan_id": f"{mode}-{site_count}",
        "mode": mode,
        "site_count": site_count,
        "sites": sites,
        "impact": impact,
        "top_improvements": [
            {
                "mesh_code": str(metrics.iloc[index]["mesh_code"]),
                "area_label": metrics.iloc[index]["area_label"],
                **mesh_results[str(metrics.iloc[index]["mesh_code"])],
            }
            for index in top_indices
            if result["score_reduction"][index] > 0
        ],
        "mesh_results": mesh_results,
    }


def _build_interventions(
    metrics_all: pd.DataFrame,
    robust_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    metrics = metrics_all.loc[metrics_all["rank_c_unfiltered"].notna()].copy().reset_index(drop=True)
    pool, road_inventory = _candidate_pool()
    transformer = Transformer.from_crs(WEB_CRS, ANALYSIS_CRS, always_xy=True)
    mesh_x, mesh_y = transformer.transform(metrics["centroid_lon"], metrics["centroid_lat"])
    candidate_x = pool["candidate_x"].to_numpy(float)
    candidate_y = pool["candidate_y"].to_numpy(float)
    point_distances = np.hypot(
        candidate_x[:, None] - np.asarray(mesh_x)[None, :],
        candidate_y[:, None] - np.asarray(mesh_y)[None, :],
    )
    primary = metrics["primary_eligible"].astype(bool).to_numpy()
    primary_indices = np.flatnonzero(primary)
    primary_distance = metrics["nearest_public_transport_distance_m"].to_numpy(float)[primary_indices]
    worst_count = max(1, int(np.ceil(len(primary_indices) * 0.1)))
    worst_decile = primary_indices[np.argsort(-primary_distance, kind="mergesort")[:worst_count]]
    robust_codes = [row["mesh_code"] for row in robust_rows[:20]]
    robust_indices = np.asarray(
        [metrics.index[metrics["mesh_code"].astype(str).eq(code)][0] for code in robust_codes],
        dtype=int,
    )
    candidate_ids = pool["road_id"].astype(str).tolist()

    def evaluate(indices: list[int]) -> dict[str, Any]:
        return evaluate_intervention(
            metrics,
            point_distances,
            indices,
            worst_decile_indices=worst_decile,
            robust_indices=robust_indices,
        )

    objective_keys = {
        "overall": lambda result: (
            result["objective_values"]["total_score_c_reduction"],
            result["objective_values"]["total_transport_distance_reduction_m"],
        ),
        "fairness": lambda result: (
            result["objective_values"]["worst_decile_mean_reduction_m"],
            result["objective_values"]["worst_decile_improved_count"],
            result["objective_values"]["total_score_c_reduction"],
        ),
        "robust": lambda result: (
            result["objective_values"]["robust_top20_improved_count"],
            result["objective_values"]["robust_top20_median_reduction_m"],
            result["objective_values"]["total_score_c_reduction"],
        ),
    }
    plans: dict[str, dict[str, Any]] = {}
    selected_by_mode: dict[str, list[int]] = {}
    for mode, objective_key in objective_keys.items():
        selected, _ = greedy_select(
            len(pool),
            3,
            evaluate,
            objective_key,
            candidate_ids,
            candidate_x,
            candidate_y,
            minimum_separation_m=MIN_CANDIDATE_SEPARATION_M,
        )
        selected_by_mode[mode] = selected
        plans[mode] = {}
        for site_count in (1, 2, 3):
            prefix = selected[:site_count]
            plans[mode][str(site_count)] = _serialize_plan(
                mode, site_count, prefix, evaluate(prefix), pool, metrics
            )

    one_site_objectives = {}
    extra_objectives = {
        "affected_elderly": lambda result: (
            result["objective_values"]["affected_elderly_population"],
            result["objective_values"]["total_score_c_reduction"],
        ),
        "mean_distance": lambda result: (
            result["objective_values"]["mean_improvement_among_improved_m"],
            result["objective_values"]["total_score_c_reduction"],
        ),
    }
    for mode, objective_key in extra_objectives.items():
        selected, result = greedy_select(
            len(pool),
            1,
            evaluate,
            objective_key,
            candidate_ids,
            candidate_x,
            candidate_y,
            minimum_separation_m=MIN_CANDIDATE_SEPARATION_M,
        )
        one_site_objectives[mode] = _serialize_plan(mode, 1, selected, result, pool, metrics)

    baseline = {
        "site_count": 0,
        "improved_mesh_count": 0,
        "affected_elderly_population": 0,
        "mean_improvement_among_improved_m": 0.0,
        "total_score_c_reduction": 0.0,
    }
    diminishing = [baseline]
    for site_count in (1, 2, 3):
        impact = plans["overall"][str(site_count)]["impact"]
        diminishing.append({"site_count": site_count, **impact})

    runtime_seconds = round(time.perf_counter() - started, 3)
    source_hashes = {
        "maizuru_mesh_metrics.csv": _sha256(METRICS_CSV),
        "final_audit.json": _sha256(FINAL_AUDIT),
        "plateau_citygml_zip": _sha256(CITYGML_ZIP),
        "p11_bus_stops": _sha256(BUS_STOPS),
        "plateau_stations": _sha256(STATIONS),
    }
    metadata = {
        "algorithm": (
            "1-site: exact evaluation of every screened road anchor. 2/3-site: deterministic "
            "forward greedy addition; each stage evaluates every spacing-eligible anchor."
        ),
        "exactness": "1-site exact within candidate pool; 2/3-site approximate greedy, not global optimum",
        "candidate_count": len(pool),
        "comparison_mesh_count": len(metrics),
        "constraints": {
            "existing_transport_exclusion_m": MIN_EXISTING_TRANSPORT_DISTANCE_M,
            "minimum_site_separation_m": MIN_CANDIDATE_SEPARATION_M,
            "candidate_geometry": "Project PLATEAU Maizuru 2025 road LOD1 surface representative points",
        },
        "objectives": {
            "overall": "maximize aggregate Score C reduction; total distance reduction is tie-breaker",
            "fairness": (
                f"maximize mean transport-distance reduction across the {len(worst_decile)} Primary meshes "
                "in the worst baseline transport-distance decile"
            ),
            "robust": (
                "maximize number of Robust Top 20 meshes with shorter distance, then their median reduction"
            ),
        },
        "seed": None,
        "runtime_seconds": runtime_seconds,
        "source_data_hashes": source_hashes,
        "generated_at": _generated_at(),
        "road_inventory": road_inventory,
    }
    report = {
        "schema_version": "1.0.0",
        "metadata": metadata,
        "baseline": baseline,
        "plans": plans,
        "one_site_objective_comparison": one_site_objectives,
        "diminishing_returns": diminishing,
        "policy_alternatives_at_two_sites": [
            plans["overall"]["2"],
            plans["fairness"]["2"],
            plans["robust"]["2"],
        ],
        "limitations": [
            "仮想交通支援拠点以外は公式データ。道路面代表点は利用可能な用地を意味しない。",
            "効果は500mメッシュ中心からの直線距離で、徒歩経路・坂・横断・運行を含まない。",
            "2/3地点は決定論的greedy近似で、全組合せの大域的最適解ではない。",
            "人口は距離が短くなるメッシュの記録値で、利用者・需要・受益者予測ではない。",
        ],
    }
    verification_context = {
        "metrics": metrics,
        "point_distances": point_distances,
        "pool": pool,
        "worst_decile": worst_decile,
        "robust_indices": robust_indices,
        "selected_by_mode": selected_by_mode,
    }
    return report, verification_context


def _evidence(
    robustness: dict[str, Any],
    interventions: dict[str, Any],
) -> dict[str, Any]:
    audit = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))
    rank_one = audit["cities"]["maizuru"]["rank_one_audit"]
    score = rank_one["score"]
    return {
        "schema_version": "1.0.0",
        "generated_at": _generated_at(),
        "philosophy": "生成AIの説明ではなく、公式データ・座標系・式・丸め前の値を追跡する。",
        "rank_one": {
            "mesh_code": rank_one["mesh_code"],
            "transport": {
                "origin": "500m mesh centroid",
                "origin_coordinates": rank_one["centroid"],
                "destination": rank_one["nearest"]["bus_stop"]["name"],
                "dataset": "国土数値情報 P11 2022",
                "crs": ANALYSIS_CRS,
                "calculation": "Euclidean distance",
                "value_m": rank_one["nearest"]["bus_stop"]["distance_m"],
            },
            "medical": {
                "origin": "500m mesh centroid",
                "destination": rank_one["nearest"]["medical"]["name"],
                "dataset": "国土数値情報 P04 2020",
                "crs": ANALYSIS_CRS,
                "calculation": "Euclidean distance",
                "value_m": rank_one["nearest"]["medical"]["distance_m"],
            },
            "score_c": {
                "formula": "elderly_population_percentile × transport_distance_percentile × medical_distance_percentile",
                "components": {
                    "elderly_population_percentile": score["elderly_population_percentile"],
                    "transport_distance_percentile": score["transport_distance_percentile"],
                    "medical_distance_percentile": score["medical_distance_percentile"],
                },
                "value": score["score_c"],
            },
            "robustness": next(
                row
                for row in robustness["candidates"]
                if row["mesh_code"] == rank_one["mesh_code"]
            ),
        },
        "intervention": {
            "formula": "after_distance(i) = min(before_distance(i), distance(mesh centroid i, each virtual point))",
            "percentile": "after distances are reranked with pandas-compatible average percentile ranks",
            "plans": {
                mode: {
                    count: {
                        "sites": plan["sites"],
                        "impact": plan["impact"],
                    }
                    for count, plan in mode_plans.items()
                }
                for mode, mode_plans in interventions["plans"].items()
            },
            "source_data_hashes": interventions["metadata"]["source_data_hashes"],
        },
    }


def build() -> dict[str, Any]:
    metrics = gpd.read_file(ROOT / "analysis/outputs/real/maizuru_city_gap.geojson")
    metrics["mesh_code"] = metrics["mesh_code"].astype(str)
    for column in (
        "population",
        "elderly_population",
        "elderly_ratio",
        "centroid_lon",
        "centroid_lat",
        "nearest_public_transport_distance_m",
        "nearest_medical_distance_m",
        "elderly_population_percentile",
        "elderly_ratio_percentile",
        "transport_distance_percentile",
        "medical_distance_percentile",
        "exploratory_score_c",
        "rank_c_unfiltered",
    ):
        metrics[column] = pd.to_numeric(metrics[column], errors="coerce")
    metrics["area_label"] = [
        _area_label(name, transport_type)
        for name, transport_type in zip(
            metrics["nearest_public_transport_name"],
            metrics["nearest_public_transport_type"],
        )
    ]
    robustness, robust_rows = _build_robustness(metrics)
    interventions, _ = _build_interventions(metrics, robust_rows)
    evidence = _evidence(robustness, interventions)

    _write_json(ROBUSTNESS_OUTPUT, robustness)
    _write_json(WEB_ROBUSTNESS, robustness, compact=True)
    with ROBUST_CSV.open("w", encoding="utf-8", newline="") as stream:
        fields = [
            "robust_rank",
            "mesh_code",
            "area_label",
            "scenario_count",
            "ranked_scenario_count",
            "top10_frequency",
            "top20_frequency",
            "pareto_frequency",
            "median_rank",
            "rank_min",
            "rank_max",
        ]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(robust_rows)
    for site_count, path in INTERVENTION_OUTPUTS.items():
        _write_json(path, interventions["plans"]["overall"][str(site_count)])
    _write_json(FAIRNESS_OUTPUT, {"metadata": interventions["metadata"], "plans": interventions["plans"]["fairness"]})
    _write_json(ROBUST_OUTPUT, {"metadata": interventions["metadata"], "plans": interventions["plans"]["robust"]})
    _write_json(WEB_INTERVENTIONS, interventions, compact=True)
    _write_json(WEB_EVIDENCE, evidence, compact=True)
    manifest = json.loads(WEB_MANIFEST.read_text(encoding="utf-8"))
    decision_outputs = {
        "robustness.json": (WEB_ROBUSTNESS, len(robustness["candidates"])),
        "intervention_scenarios.json": (WEB_INTERVENTIONS, 9),
        "evidence.json": (WEB_EVIDENCE, 1),
    }
    retained = [
        output
        for output in manifest.get("outputs", [])
        if output.get("file") not in decision_outputs
    ]
    manifest["outputs"] = retained + [
        {
            "file": filename,
            "status": "available",
            "records": records,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for filename, (path, records) in decision_outputs.items()
    ]
    manifest["decision_studio"] = {
        "scenario_count": robustness["scenario_count"],
        "candidate_count": interventions["metadata"]["candidate_count"],
        "algorithm": interventions["metadata"]["algorithm"],
        "exactness": interventions["metadata"]["exactness"],
    }
    _write_json(WEB_MANIFEST, manifest)
    return {
        "robustness": robustness,
        "interventions": interventions,
        "evidence": evidence,
    }


if __name__ == "__main__":
    result = build()
    print(
        json.dumps(
            {
                "scenario_count": result["robustness"]["scenario_count"],
                "robust_rank_one": result["robustness"]["top_candidates"][0],
                "candidate_count": result["interventions"]["metadata"]["candidate_count"],
                "runtime_seconds": result["interventions"]["metadata"]["runtime_seconds"],
                "diminishing_returns": result["interventions"]["diminishing_returns"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

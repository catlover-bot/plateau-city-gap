from __future__ import annotations

from fastapi.testclient import TestClient

from backend.citygap_platform.api.app import create_app
from backend.citygap_platform.api.repository import PostGISRepository


def _headers(role: str) -> dict[str, str]:
    return {"X-CITYGAP-Actor": f"integration-{role}", "X-CITYGAP-Roles": role}


def test_validation_schema_seed_spatial_api_review_and_audit(database_url: str) -> None:
    import psycopg

    repository = PostGISRepository(database_url)
    client = TestClient(create_app(repository))
    claims = client.get("/validation/claims", headers=_headers("viewer"))
    assert claims.status_code == 200
    assert len(claims.json()["claims"]) == 9

    request = {
        "claim_key": "experimental_network_accessibility",
        "method_key": "osm_reference_comparison",
        "dataset_versions": {"plateau": "2025", "osm": "2026-08-27"},
        "network_version_id": "40000000-0000-0000-0000-000000000001",
        "algorithm_version": "network-cross-validation-v1.0.0",
        "reference_source": {"semantics": "reference_network", "license": "ODbL"},
        "sample_rule": {"method": "deterministic_stratified", "minimum": 100},
        "limitations": ["not field ground truth"],
    }
    created = client.post(
        "/cities/maizuru/validation", json=request, headers=_headers("analyst")
    )
    assert created.status_code == 201
    validation_id = created.json()["validation_id"]

    with psycopg.connect(database_url) as connection:
        sample_id = connection.execute(
            """INSERT INTO validation_samples (
                   validation_run_id, sample_key, strata, origin_reference,
                   destination_reference, origin_snap, destination_snap,
                   sampling_rank, geometry, metadata
               ) VALUES (%s, 'integration-route-1', ARRAY['coastal','long_distance'],
                   'building:fixture', 'medical:fixture', '{"distance_m":12}',
                   '{"distance_m":8}', 1,
                   ST_GeomFromText('LINESTRING(135.31 35.45,135.34 35.48)',4326), '{}')
               RETURNING id""",
            (validation_id,),
        ).fetchone()[0]
        result_id = connection.execute(
            """INSERT INTO validation_results (
                   validation_run_id, validation_sample_id, result_key,
                   primary_model, reference_model, metrics, known_limitation,
                   sensitivity_evidence, reference_agreement, coverage,
                   validation_status, evidence_strength
               ) VALUES (%s,%s,'integration-result-1','experimental_surface_adjacency',
                   'osm_reference_network','{"primary_m":500,"reference_m":1100}',
                   'reference is not field ground truth','{"tested":true}',
                   'large_difference','{"covered":true}','cross_validated',
                   '{"source_verified":"YES","reproducible":"YES","independent_verifier":"YES","reference_model_agreement":"YES","assumption_sensitive":"YES","municipal_review":"NO","field_verified":"NO"}')
               RETURNING id""",
            (validation_id, sample_id),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO validation_disagreements (
                   validation_run_id, validation_sample_id, disagreement_class,
                   primary_value, reference_value, cause_candidate, cause_rule,
                   priority_rank, geometry
               ) VALUES (%s,%s,'large_difference','{"distance_m":500}',
                   '{"distance_m":1100}','topology','deterministic fixture rule',1,
                   ST_GeomFromText('LINESTRING(135.31 35.45,135.34 35.48)',4326))""",
            (validation_id, sample_id),
        )
        connection.execute(
            """INSERT INTO model_uncertainty (
                   claim_key, validation_run_id, category, known_limitation,
                   sensitivity_evidence, reference_agreement, coverage, validation_status
               ) VALUES ('experimental_network_accessibility',%s,'network_semantics',
                   'crossings and permissions differ','{"models":2}',
                   'large_difference','{"sample":1}','cross_validated')""",
            (validation_id,),
        )
        connection.commit()

    bbox = "135,35,136,36"
    assert client.get(
        f"/validation/{validation_id}/samples", params={"bbox": bbox}, headers=_headers("viewer")
    ).json()["features"][0]["sample_key"] == "integration-route-1"
    assert client.get(
        f"/validation/{validation_id}/disagreements",
        params={"bbox": bbox}, headers=_headers("viewer"),
    ).json()["features"][0]["cause_candidate"] == "topology"
    assert client.get(
        f"/validation/{validation_id}/sensitivity", headers=_headers("viewer")
    ).json()["aggregation_score"] is None

    review = client.post(
        f"/validation/{validation_id}/field-review",
        json={
            "validation_result_id": str(result_id),
            "observation_type": "road_passability",
            "road_passability": "uncertain",
            "longitude": 135.32,
            "latitude": 35.46,
            "observed_at": "2026-08-27T12:00:00+09:00",
            "municipal_feedback": "not_reviewed",
            "review_note": "integration fixture only",
        },
        headers=_headers("planner"),
    )
    assert review.status_code == 201
    assert review.json()["status"] == "submitted"
    with psycopg.connect(database_url) as connection:
        actions = {row[0] for row in connection.execute(
            "SELECT action FROM audit_log WHERE resource_type IN ('validation_run','field_validation')"
        ).fetchall()}
    assert {"validation.run.create", "validation.field_review.create"} <= actions

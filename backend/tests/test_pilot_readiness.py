from backend.citygap_platform.readiness import PilotCheck, classify_readiness


def test_pilot_readiness_has_three_reasoned_states() -> None:
    ready = classify_readiness([PilotCheck("database", True, True, "ok")])
    assert ready["status"] == "READY"
    limited = classify_readiness(
        [
            PilotCheck("database", True, True, "ok"),
            PilotCheck("gtfs", False, False, "not published", "record unavailable"),
        ]
    )
    assert limited["status"] == "READY_WITH_LIMITATIONS"
    assert limited["limitations"] == ["gtfs"]
    blocked = classify_readiness(
        [PilotCheck("migrations", False, True, "behind", "apply migrations")]
    )
    assert blocked["status"] == "NOT_READY"
    assert blocked["blockers"] == ["migrations"]

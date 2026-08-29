from analysis.src.urban_section import TerrainTriangle, sample_tin_transect, section_relations


def test_tin_section_uses_barycentric_height_and_reports_no_coverage() -> None:
    triangle = TerrainTriangle(
        "tin-1",
        (
            (135.3960, 35.4470, 10.0),
            (135.3970, 35.4470, 20.0),
            (135.3960, 35.4480, 30.0),
        ),
    )
    samples = sample_tin_transect(
        [[135.3959, 35.4472], [135.3968, 35.4472]],
        [triangle],
        sample_interval_m=20,
    )
    assert any(sample.elevation_m is not None for sample in samples)
    assert any(sample.quality == "no_coverage" for sample in samples)
    assert all(
        sample.source_triangle_id == "tin-1"
        for sample in samples
        if sample.elevation_m is not None
    )


def test_section_relations_separate_direct_and_nearby() -> None:
    objects = [
        {
            "id": "direct",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[135.3964, 35.4474], [135.3966, 35.4474], [135.3966, 35.4476], [135.3964, 35.4476], [135.3964, 35.4474]]],
            },
            "properties": {},
        },
        {
            "id": "nearby",
            "geometry": {"type": "Point", "coordinates": [135.3968, 35.44755]},
            "properties": {},
        },
    ]
    relations = section_relations(
        [[135.3960, 35.4475], [135.3970, 35.4475]], objects, buffer_m=10
    )
    assert {item["source_object_id"]: item["relation"] for item in relations} == {
        "direct": "direct",
        "nearby": "nearby",
    }

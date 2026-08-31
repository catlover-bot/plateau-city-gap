import pytest
from shapely.geometry import Polygon, mapping

from backend.citygap_platform.domain.investigation_area import (
    AreaActionType,
    AreaKnowledgeItem,
    AreaKnowledgeStatus,
    AreaOriginKind,
    KnowledgeReason,
    PointRadiusDefinition,
    RadiusMethodology,
    WeightedObservation,
    area_weighted_estimate,
    build_point_radius_geometry,
    select_important_unknowns,
    validate_radius,
)


@pytest.mark.parametrize(
    ("radius", "methodology"),
    [
        (100, RadiusMethodology.CUSTOM_RADIUS),
        (500, RadiusMethodology.MLIT_ELDERLY_WALK_REFERENCE_500M),
        (650, RadiusMethodology.CUSTOM_RADIUS),
        (800, RadiusMethodology.MLIT_GENERAL_WALK_REFERENCE_800M),
        (1000, RadiusMethodology.BROAD_CONTEXT_1000M),
        (3000, RadiusMethodology.CUSTOM_RADIUS),
    ],
)
def test_radius_contract_accepts_only_bounded_consistent_integer_values(radius, methodology):
    assert validate_radius(radius, methodology) == radius


@pytest.mark.parametrize("radius", [99, 3001, -1, 500.0, True])
def test_radius_contract_rejects_out_of_bounds_and_non_integer_values(radius):
    with pytest.raises((TypeError, ValueError)):
        validate_radius(radius, RadiusMethodology.CUSTOM_RADIUS)


def test_radius_methodology_cannot_mislabel_a_radius():
    with pytest.raises(ValueError):
        validate_radius(800, RadiusMethodology.MLIT_ELDERLY_WALK_REFERENCE_500M)
    with pytest.raises(ValueError):
        validate_radius(800, RadiusMethodology.CUSTOM_RADIUS)


def test_station_and_map_point_use_the_same_point_radius_contract():
    station = PointRadiusDefinition(
        origin_kind=AreaOriginKind.STATION,
        longitude=135.3305425686,
        latitude=35.4417242947,
        radius_m=800,
        radius_methodology=RadiusMethodology.MLIT_GENERAL_WALK_REFERENCE_800M,
        source_dataset_version_id="gtfs-maizuru@2025",
        source_feature_id="station-007",
    )
    map_point = PointRadiusDefinition(
        origin_kind=AreaOriginKind.MAP_POINT,
        longitude=135.3305425686,
        latitude=35.4417242947,
        radius_m=800,
        radius_methodology=RadiusMethodology.MLIT_GENERAL_WALK_REFERENCE_800M,
    )
    assert station.radius_m == map_point.radius_m == 800
    with pytest.raises(ValueError):
        PointRadiusDefinition(
            origin_kind=AreaOriginKind.STATION,
            longitude=135.33,
            latitude=35.44,
            radius_m=800,
            radius_methodology=RadiusMethodology.MLIT_GENERAL_WALK_REFERENCE_800M,
        )


def test_point_radius_is_buffered_in_projected_crs_and_clipped_honestly():
    area = PointRadiusDefinition(
        origin_kind=AreaOriginKind.MAP_POINT,
        longitude=135.3305425686,
        latitude=35.4417242947,
        radius_m=800,
        radius_methodology=RadiusMethodology.MLIT_GENERAL_WALK_REFERENCE_800M,
    )
    whole = build_point_radius_geometry(area)
    assert whole.requested_geometry["type"] == "Polygon"
    assert whole.effective_geometry == whole.requested_geometry
    assert whole.clipped_area_ratio == pytest.approx(1.0)
    assert len(whole.geometry_sha256) == 64

    half_boundary = mapping(
        Polygon(
            [
                (135.3305, 35.43),
                (135.3450, 35.43),
                (135.3450, 35.455),
                (135.3305, 35.455),
            ]
        )
    )
    clipped = build_point_radius_geometry(area, city_boundary=half_boundary)
    assert 0 < clipped.clipped_area_ratio < 1


def test_area_weighting_never_replaces_missing_or_suppressed_values_with_zero():
    result = area_weighted_estimate(
        [
            WeightedObservation(value=100, overlap_ratio=0.5),
            WeightedObservation(value=None, overlap_ratio=0.25),
            WeightedObservation(value=999, overlap_ratio=0.25, suppressed=True),
        ]
    )
    assert result.value == 50
    assert result.coverage_ratio == 0.5
    assert result.contributing_records == 1


def _knowledge(
    key: str,
    impact: int,
    *,
    action: AreaActionType = AreaActionType.FIELD_VERIFICATION,
    status: AreaKnowledgeStatus = AreaKnowledgeStatus.UNKNOWN,
) -> AreaKnowledgeItem:
    return AreaKnowledgeItem(
        key=key,
        status=status,
        action_type=action,
        reason_code=KnowledgeReason.REQUIRES_FIELD_OBSERVATION,
        importance=f"{key} can change the municipal interpretation",
        decision_impact=impact,
        source_references=("dataset-version-1",),
    )


def test_only_field_verifiable_unknowns_become_at_most_four_public_items():
    selected = select_important_unknowns(
        [
            _knowledge("fifth", 50),
            _knowledge("first", 100),
            _knowledge("second", 90),
            _knowledge("third", 80),
            _knowledge("fourth", 70),
            _knowledge("acquire", 99, action=AreaActionType.DATA_ACQUISITION),
            _knowledge("known", 98, status=AreaKnowledgeStatus.KNOWN, action=AreaActionType.NONE),
        ]
    )
    assert [item.key for item in selected] == ["first", "second", "third", "fourth"]


def test_known_status_cannot_hide_partial_coverage():
    with pytest.raises(ValueError):
        AreaKnowledgeItem(
            key="population",
            status=AreaKnowledgeStatus.KNOWN,
            action_type=AreaActionType.NONE,
            reason_code=KnowledgeReason.COVERAGE_GAP,
            importance="Population is a primary municipal context.",
            decision_impact=80,
            source_references=("census-2020",),
            coverage_ratio=0.8,
        )

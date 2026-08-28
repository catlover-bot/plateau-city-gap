-- Municipal open-data analysis catalog V2 and review-candidate finding types.
-- This is forward-only: existing definitions and findings remain valid.

ALTER TABLE findings DROP CONSTRAINT findings_finding_type_check;
ALTER TABLE findings ADD CONSTRAINT findings_finding_type_check CHECK (
    finding_type IN (
        'accessibility_gap', 'care_access_review_candidate',
        'activity_service_gap_candidate', 'network_criticality',
        'planning_context', 'temporal_change', 'resilience_impact',
        'data_quality_issue'
    )
);

INSERT INTO analysis_definitions (
    id, version, name, purpose, required_capabilities,
    input_contract, output_contract, algorithm_description, claim_boundary
) VALUES
(
    'medical-access-v2', '2.0.0', 'Medical Access V2',
    '公式医療機関点と500mメッシュの距離文脈を追加調査候補として確認する',
    ARRAY['screening','medical'],
    '{"required":["urban_state","population_500m","mhlw_medical_facilities"],"context_roles":["urban_state"],"dataset_roles":["population_500m","mhlw_medical_facilities"]}',
    '{"produces":["medical_access_context","finding"]}',
    'Projected straight-line mesh-centroid distance with independent source metrics',
    '直線距離は到達時間、診療可否、受入能力、医療不足、政策優先順位ではない。'
),
(
    'care-access', '1.0.0', 'Care Access',
    '高齢者人口、公式介護事業所、PLATEAU空間文脈から現地確認候補を抽出する',
    ARRAY['screening','building_detail','care'],
    '{"required":["urban_state","elderly_population_500m","mhlw_care_facilities","plateau_buildings"],"context_roles":["urban_state"],"dataset_roles":["elderly_population_500m","mhlw_care_facilities","plateau_buildings"]}',
    '{"produces":["care_access_context","care_access_review_candidate"]}',
    'Independent threshold conjunction over disclosed population and distance context',
    '候補は介護不足、需要、利用資格、空床、政策優先順位の認定ではない。'
),
(
    'future-population-spatial', '1.0.0', '将来公式人口の空間比較',
    '公式250m将来人口系列を500mメッシュへ決定論的に集約して年度間を比較する',
    ARRAY['screening','future_population'],
    '{"required":["urban_state","mlit_future_population_250m"],"context_roles":["urban_state"],"dataset_roles":["mlit_future_population_250m"]}',
    '{"produces":["future_population_mesh_context"]}',
    'Deterministic JIS mesh parent aggregation with explicit temporal separation',
    '公式試算は観測値や保証された予測ではなく、最良シナリオを自動選択しない。'
),
(
    'daytime-activity-context', '1.0.0', 'Daytime Activity Context',
    '事業所・従業者集積をサービス到達文脈と別々の指標で確認する',
    ARRAY['screening','economic_activity'],
    '{"required":["economic_census_500m","urban_state"],"context_roles":["urban_state"],"dataset_roles":["economic_census_500m"]}',
    '{"produces":["activity_service_context","activity_service_gap_candidate"]}',
    'Published activity counts joined to separate service-distance context',
    '従業者数は昼間人口、サービス需要、混雑、政策上の不足を意味しない。'
),
(
    'earthquake-ground-context', '1.0.0', 'Earthquake / Ground Context',
    'J-SHIS表層地盤モデルを監査対象500mメッシュへ集約する',
    ARRAY['screening','ground'],
    '{"required":["jshis_ground_250m","urban_state"],"context_roles":["urban_state"],"dataset_roles":["jshis_ground_250m"]}',
    '{"produces":["ground_context"]}',
    'Deterministic 250m-to-500m model-cell aggregation',
    '地盤モデル値は地震確率、被害予測、危険度、政策リスクスコアではない。'
),
(
    'historical-traffic-safety-context', '1.0.0', 'Historical Traffic Safety Context',
    '人身事故履歴を500mメッシュで集計し現地調査の文脈として表示する',
    ARRAY['screening','traffic_accident'],
    '{"required":["npa_historical_accidents","urban_state"],"context_roles":["urban_state"],"dataset_roles":["npa_historical_accidents"]}',
    '{"produces":["historical_accident_context"]}',
    'Historical event aggregation with unmatched records preserved separately',
    '事故件数は交通量で正規化しておらず、現在の危険度、原因、確率、予測ではない。'
);

INSERT INTO analysis_dataset_requirements (
    analysis_id, analysis_version, dataset_family, requirement_level,
    source_selection_rule, rule_version
) VALUES
('accessibility-gap','1.0.0','census_population_500m','required','{"policy":"latest promoted official mesh version"}','open-data-source-preference@1'),
('accessibility-gap','1.0.0','facilities','required','{"policy":"promoted facilities matching the analysis reference state"}','open-data-source-preference@1'),
('accessibility-gap','1.0.0','plateau_buildings','required','{"policy":"current validated PLATEAU building version"}','open-data-source-preference@1'),
('building-accessibility','2.0.0','plateau_buildings','required','{"policy":"current validated PLATEAU building version"}','open-data-source-preference@1'),
('building-accessibility','2.0.0','facilities','required','{"policy":"promoted facilities; do not infer identity from proximity"}','open-data-source-preference@1'),
('network-criticality','1.0.0','road_network','required','{"policy":"version-pinned graph with documented semantics"}','open-data-source-preference@1'),
('network-criticality','1.0.0','official_pedestrian_network','enhancement','{"policy":"official city-covering pedestrian graph only"}','open-data-source-preference@1'),
('stress-test','1.0.0','road_network','required','{"policy":"version-pinned graph with documented semantics"}','open-data-source-preference@1'),
('stress-test','1.0.0','hazard','required','{"policy":"official hazard layer with applicable assumptions"}','open-data-source-preference@1'),
('future-accessibility','1.0.0','future_population','required','{"policy":"official scenario kept as named scenario"}','open-data-source-preference@1'),
('future-accessibility','1.0.0','road_network','optional','{"policy":"version-pinned graph; fixed-service assumption required"}','open-data-source-preference@1'),
('temporal-diff','1.0.0','versioned_dataset_pair','required','{"policy":"two immutable versions from the same dataset identity"}','open-data-source-preference@1'),
('medical-access-v2','2.0.0','census_population_500m','required','{"policy":"latest promoted official 500m census mesh"}','open-data-source-preference@1'),
('medical-access-v2','2.0.0','mhlw_medical','required','{"policy":"latest promoted official medical-facility release"}','open-data-source-preference@1'),
('medical-access-v2','2.0.0','plateau_buildings','optional','{"policy":"current validated PLATEAU building version"}','open-data-source-preference@1'),
('medical-access-v2','2.0.0','road_network','optional','{"policy":"experimental metric displayed separately"}','open-data-source-preference@1'),
('medical-access-v2','2.0.0','official_pedestrian_network','enhancement','{"policy":"official graph covering the audited city"}','open-data-source-preference@1'),
('care-access','1.0.0','census_elderly_population_500m','required','{"policy":"official disclosed 2020 elderly population mesh"}','open-data-source-preference@1'),
('care-access','1.0.0','mhlw_care','required','{"policy":"latest promoted official care-establishment release"}','open-data-source-preference@1'),
('care-access','1.0.0','plateau_buildings','required','{"policy":"current validated PLATEAU building version"}','open-data-source-preference@1'),
('care-access','1.0.0','road_network','optional','{"policy":"experimental metric displayed separately"}','open-data-source-preference@1'),
('care-access','1.0.0','official_pedestrian_network','enhancement','{"policy":"official graph covering the audited city"}','open-data-source-preference@1'),
('care-access','1.0.0','social_participation','enhancement','{"policy":"official spatially and temporally documented source only"}','open-data-source-preference@1'),
('future-population-spatial','1.0.0','mlit_future_population_250m','required','{"policy":"official R6 trial projection series"}','open-data-source-preference@1'),
('future-population-spatial','1.0.0','census_population_500m','required','{"policy":"observed context kept temporally separate"}','open-data-source-preference@1'),
('future-population-spatial','1.0.0','plateau_buildings','optional','{"policy":"current validated PLATEAU building version"}','open-data-source-preference@1'),
('daytime-activity-context','1.0.0','economic_census_500m','required','{"policy":"latest promoted official economic-census mesh"}','open-data-source-preference@1'),
('daytime-activity-context','1.0.0','mhlw_medical','optional','{"policy":"latest promoted official medical-facility release"}','open-data-source-preference@1'),
('daytime-activity-context','1.0.0','transport_points','optional','{"policy":"promoted official transport points"}','open-data-source-preference@1'),
('daytime-activity-context','1.0.0','official_pedestrian_network','enhancement','{"policy":"official graph covering the audited city"}','open-data-source-preference@1'),
('earthquake-ground-context','1.0.0','jshis_surface_ground','required','{"policy":"published V4 250m surface-ground model"}','open-data-source-preference@1'),
('earthquake-ground-context','1.0.0','plateau_buildings','optional','{"policy":"current validated PLATEAU building version"}','open-data-source-preference@1'),
('historical-traffic-safety-context','1.0.0','npa_traffic_accident','required','{"policy":"latest promoted complete annual injury/fatal accident file"}','open-data-source-preference@1'),
('historical-traffic-safety-context','1.0.0','road_network','optional','{"policy":"version-pinned graph without event identity conflation"}','open-data-source-preference@1'),
('historical-traffic-safety-context','1.0.0','traffic_volume','enhancement','{"policy":"official stable denominator with matching coverage and period"}','open-data-source-preference@1');

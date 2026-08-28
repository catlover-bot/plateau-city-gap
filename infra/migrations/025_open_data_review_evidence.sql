-- Municipal review loop, Evidence Center V2 and public transparency records.
-- Official raw/canonical records remain immutable; feedback and overrides are
-- explicit tenant-owned layers with review and expiry boundaries.

ALTER TABLE open_data_source_feedback
    ADD COLUMN raw_mutation_permitted boolean NOT NULL DEFAULT false
        CHECK (NOT raw_mutation_permitted),
    ADD COLUMN canonical_mutation_permitted boolean NOT NULL DEFAULT false
        CHECK (NOT canonical_mutation_permitted);

CREATE TABLE open_data_field_tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    source_feedback_id uuid NOT NULL,
    canonical_record_id bigint,
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    checklist jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(checklist) = 'array'),
    status text NOT NULL DEFAULT 'open' CHECK (
        status IN ('open','assigned','in_progress','completed','cancelled')
    ),
    assigned_to text,
    due_date date,
    resolution_note text,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_by text,
    completed_at timestamptz,
    UNIQUE (organization_id, id),
    UNIQUE (organization_id, source_feedback_id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, source_feedback_id)
        REFERENCES open_data_source_feedback(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, canonical_record_id)
        REFERENCES canonical_open_data_records(organization_id, id),
    CHECK (
        (status = 'completed' AND completed_by IS NOT NULL
            AND completed_at IS NOT NULL AND resolution_note IS NOT NULL)
        OR status IN ('open','assigned','in_progress','cancelled')
    )
);
CREATE INDEX open_data_field_tasks_city_status_idx
    ON open_data_field_tasks (organization_id, city_id, status, due_date, created_at DESC);

ALTER TABLE local_data_overrides
    ADD COLUMN updated_by text,
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
    ADD COLUMN reviewed_by text,
    ADD COLUMN reviewed_at timestamptz;
UPDATE local_data_overrides
SET updated_by = created_by,
    reviewed_by = CASE WHEN review_status = 'reviewed' THEN created_by ELSE reviewed_by END,
    reviewed_at = CASE WHEN review_status = 'reviewed' THEN created_at ELSE reviewed_at END;
ALTER TABLE local_data_overrides
    ADD CONSTRAINT local_data_overrides_review_actor_check CHECK (
        (review_status = 'reviewed' AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
        OR review_status IN ('draft','in_review','rejected','superseded')
    );

CREATE INDEX local_data_overrides_review_due_idx
    ON local_data_overrides (
        organization_id, review_status, expires_at, effective_date DESC, id
    );

CREATE FUNCTION citygap_open_data_override_reconciliation_candidate() RETURNS trigger AS $$
BEGIN
    INSERT INTO open_data_override_reconciliations (
        organization_id, override_id, candidate_canonical_record_id,
        status, explanation
    )
    SELECT override.organization_id, override.id, NEW.id, 'candidate',
           '公式データ更新に同一外部識別子の候補があります。overrideは自動削除せず人が照合します。'
    FROM local_data_overrides AS override
    JOIN canonical_open_data_records AS previous
      ON previous.organization_id = override.organization_id
     AND previous.id = override.canonical_record_id
    WHERE override.organization_id = NEW.organization_id
      AND override.review_status IN ('in_review','reviewed')
      AND override.expires_at >= current_date
      AND previous.id <> NEW.id
      AND previous.city_id = NEW.city_id
      AND previous.record_type = NEW.record_type
      AND previous.external_record_id = NEW.external_record_id
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER open_data_override_reconciliation_candidate
    AFTER INSERT ON canonical_open_data_records
    FOR EACH ROW EXECUTE FUNCTION citygap_open_data_override_reconciliation_candidate();

ALTER TABLE evidence_centers ADD COLUMN schema_version text;
UPDATE evidence_centers SET schema_version = '1.0.0' WHERE schema_version IS NULL;
ALTER TABLE evidence_centers
    ALTER COLUMN schema_version SET DEFAULT '2.0.0',
    ALTER COLUMN schema_version SET NOT NULL,
    ADD COLUMN open_data_lineage_manifest jsonb NOT NULL DEFAULT '{}'
        CHECK (jsonb_typeof(open_data_lineage_manifest) = 'object'),
    ADD COLUMN report_manifest jsonb NOT NULL DEFAULT '{}'
        CHECK (jsonb_typeof(report_manifest) = 'object'),
    ADD COLUMN claim_boundary text NOT NULL DEFAULT
        '公開データとモデル結果の出典・仮定・限界を記録し、行政判断や政策効果を自動認定しません。',
    ADD COLUMN reproducibility_status text NOT NULL DEFAULT 'recorded' CHECK (
        reproducibility_status IN ('recorded','verified','failed','not_applicable')
    );

ALTER TABLE report_records ADD COLUMN content_schema_version text;
UPDATE report_records SET content_schema_version = '1.0.0'
WHERE content_schema_version IS NULL;
ALTER TABLE report_records
    ALTER COLUMN content_schema_version SET DEFAULT '2.0.0',
    ALTER COLUMN content_schema_version SET NOT NULL,
    ADD COLUMN deterministic boolean NOT NULL DEFAULT true CHECK (deterministic),
    ADD COLUMN public_summary jsonb NOT NULL DEFAULT '{}'
        CHECK (jsonb_typeof(public_summary) = 'object');

CREATE TABLE public_transparency_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    city_id uuid NOT NULL,
    report_id uuid,
    evidence_center_id uuid,
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
    summary jsonb NOT NULL CHECK (jsonb_typeof(summary) = 'object'),
    source_citations jsonb NOT NULL CHECK (jsonb_typeof(source_citations) = 'array'),
    limitations jsonb NOT NULL CHECK (jsonb_typeof(limitations) = 'array'),
    publication_status text NOT NULL DEFAULT 'draft' CHECK (
        publication_status IN ('draft','published','withdrawn')
    ),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_by text,
    published_at timestamptz,
    withdrawn_by text,
    withdrawn_at timestamptz,
    UNIQUE (organization_id, id),
    FOREIGN KEY (organization_id, city_id)
        REFERENCES cities(organization_id, id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id, report_id)
        REFERENCES report_records(organization_id, id),
    FOREIGN KEY (organization_id, evidence_center_id)
        REFERENCES evidence_centers(organization_id, id),
    CHECK (report_id IS NOT NULL OR evidence_center_id IS NOT NULL),
    CHECK (
        (publication_status = 'published' AND published_by IS NOT NULL
            AND published_at IS NOT NULL)
        OR publication_status IN ('draft','withdrawn')
    ),
    CHECK (
        (publication_status = 'withdrawn' AND withdrawn_by IS NOT NULL
            AND withdrawn_at IS NOT NULL)
        OR publication_status IN ('draft','published')
    )
);
CREATE INDEX public_transparency_records_city_status_idx
    ON public_transparency_records (
        organization_id, city_id, publication_status, published_at DESC, id
    );

CREATE FUNCTION citygap_validate_public_transparency() RETURNS trigger AS $$
DECLARE
    report_classification text;
    evidence_classification text;
BEGIN
    IF NEW.report_id IS NOT NULL THEN
        SELECT data_classification INTO report_classification
        FROM report_records
        WHERE organization_id = NEW.organization_id AND id = NEW.report_id;
        IF report_classification IS DISTINCT FROM 'public' THEN
            RAISE EXCEPTION 'public transparency requires a public report';
        END IF;
    END IF;
    IF NEW.evidence_center_id IS NOT NULL THEN
        SELECT data_classification INTO evidence_classification
        FROM evidence_centers
        WHERE organization_id = NEW.organization_id AND id = NEW.evidence_center_id;
        IF evidence_classification IS DISTINCT FROM 'public' THEN
            RAISE EXCEPTION 'public transparency requires public evidence';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER public_transparency_classification_gate
    BEFORE INSERT OR UPDATE ON public_transparency_records
    FOR EACH ROW EXECUTE FUNCTION citygap_validate_public_transparency();

COMMENT ON TABLE open_data_field_tasks IS
    'Field verification tasks derived from feedback without mutating official raw/canonical data.';
COMMENT ON TRIGGER open_data_override_reconciliation_candidate ON canonical_open_data_records IS
    'Creates human reconciliation candidates for official updates; never deletes local overrides.';
COMMENT ON TABLE public_transparency_records IS
    'Reviewed public summaries backed only by public-classified deterministic reports/evidence.';

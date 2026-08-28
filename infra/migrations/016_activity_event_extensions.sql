BEGIN;

ALTER TABLE activity_events
    DROP CONSTRAINT activity_events_event_type_check;
ALTER TABLE activity_events
    ADD CONSTRAINT activity_events_event_type_check CHECK (
        event_type IN (
            'dataset_updated', 'finding_created', 'investigation_started',
            'scenario_compared', 'review_submitted', 'field_check_added',
            'decision_recorded', 'urban_state_promoted',
            'finding_status_changed', 'review_status_changed',
            'investigation_status_changed', 'analysis_started',
            'saved_view_created'
        )
    );

COMMIT;

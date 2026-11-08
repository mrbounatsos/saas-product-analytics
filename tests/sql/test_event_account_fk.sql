
BEGIN;

-- 1. Create two valid accounts.
INSERT INTO accounts (
    account_id, created_at, company_name,
    segment, country, acquisition_channel, employee_band
)
VALUES
    (999001, '2026-01-01', 'Company A',
     'smb', 'NL', 'organic', 10),
    (999002, '2026-01-01', 'Company B',
     'smb', 'NL', 'organic', 20);

-- 2. Create a user belonging to Company A.
INSERT INTO users (
    user_id, account_id, created_at, role
)
VALUES (
    999001, 999001, '2026-01-02', 'admin'
);

-- 3. Test the composite foreign key.
DO $$
DECLARE
    violated_constraint TEXT;
    rejected BOOLEAN := FALSE;
BEGIN
    BEGIN
        -- User 999001 belongs to account 999001,
        -- but this event references account 999002.
        INSERT INTO events (
            event_id, user_id, account_id,
            event_name, event_time, ingested_at
        )
        VALUES (
            999001, 999001, 999002,
            'login', '2026-01-03', '2026-01-03'
        );

    EXCEPTION
        WHEN foreign_key_violation THEN
            GET STACKED DIAGNOSTICS
                violated_constraint = CONSTRAINT_NAME;

            IF violated_constraint <> 'fk_events_user_account' THEN
                RAISE EXCEPTION
                    'TEST FAILED: unexpected constraint %',
                    violated_constraint;
            END IF;

            rejected := TRUE;
    END;

    IF NOT rejected THEN
        RAISE EXCEPTION
            'TEST FAILED: invalid event was accepted';
    END IF;

    RAISE NOTICE
        'TEST PASSED: event-account mismatch rejected';
END $$;

-- 4. Remove all test data.
ROLLBACK;

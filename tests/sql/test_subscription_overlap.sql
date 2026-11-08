BEGIN;

INSERT INTO accounts (
    account_id, created_at, company_name,
    segment, country, acquisition_channel, employee_band
)
VALUES (
    999001, '2026-01-01', 'Test Company',
    'smb', 'NL', 'organic', 10
);

INSERT INTO plans (
    plan_id, plan_name, monthly_price_per_seat_cents
)
VALUES (9999, 'Test Plan', 1200);

INSERT INTO subscriptions (
    subscription_id, account_id, plan_id,
    started_at, ended_at, seat_count,
    billing_interval, mrr_cents
)
VALUES (
    999001, 999001, 9999,
    '2026-01-01', '2026-04-01',
    5, 'monthly', 6000
);

DO $$
BEGIN
    INSERT INTO subscriptions (
        subscription_id, account_id, plan_id,
        started_at, ended_at, seat_count,
        billing_interval, mrr_cents
    )
    VALUES (
        999002, 999001, 9999,
        '2026-03-01', '2026-06-01',
        5, 'monthly', 6000
    );

    RAISE EXCEPTION
        'TEST FAILED: overlapping subscription was accepted';

EXCEPTION
    WHEN exclusion_violation THEN
        RAISE NOTICE
            'TEST PASSED: overlapping subscription rejected';
END $$;

ROLLBACK;
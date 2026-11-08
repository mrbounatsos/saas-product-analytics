
BEGIN;

-- Create two valid accounts
INSERT INTO accounts (
    account_id, created_at, company_name,
    segment, country, acquisition_channel, employee_band
)
VALUES
    (999001, '2026-01-01', 'Company A',
     'smb', 'NL', 'organic', 10),
    (999002, '2026-01-01', 'Company B',
     'smb', 'NL', 'organic', 20);

-- Create a paid subscription plan
INSERT INTO plans (
    plan_id, plan_name, monthly_price_per_seat_cents
)
VALUES (
    9999, 'Test Pro', 5000
);

-- Create a subscription belonging to Company A
INSERT INTO subscriptions (
    subscription_id, account_id, plan_id,
    started_at, seat_count,
    billing_interval, mrr_cents
)
VALUES (
    8888, 999001, 9999,
    '2026-01-01', 1,
    'monthly', 5000
);

-- Attempt to assign Company A's subscription to Company B
DO $$
DECLARE
    violated_constraint TEXT;
    rejected BOOLEAN := FALSE;
BEGIN
    BEGIN
        INSERT INTO invoices (
            invoice_id, account_id, subscription_id,
            invoice_date, amount_cents,
            status, paid_at
        )
        VALUES (
            5555, 999002, 8888,
            '2026-01-01', 5000,
            'paid', '2026-01-01'
        );

    EXCEPTION
        WHEN foreign_key_violation THEN
            GET STACKED DIAGNOSTICS
                violated_constraint = CONSTRAINT_NAME;

            IF violated_constraint <> 'fk_invoices_subscription_account' THEN
                RAISE EXCEPTION
                    'TEST FAILED: unexpected constraint %',
                    violated_constraint;
            END IF;

            rejected := TRUE;
    END;

    IF NOT rejected THEN
        RAISE EXCEPTION
            'TEST FAILED: invalid invoice was accepted';
    END IF;

    RAISE NOTICE
        'TEST PASSED: invoice-subscription mismatch rejected';
END $$;

ROLLBACK;

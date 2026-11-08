CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS accounts (
    account_id BIGINT PRIMARY KEY,

    created_at TIMESTAMPTZ NOT NULL,

    company_name TEXT NOT NULL
        CHECK (LENGTH(TRIM(company_name)) > 0),

    segment TEXT NOT NULL
        CHECK (segment IN ('smb', 'mid_market', 'enterprise')),

    country CHAR(2) NOT NULL,

    acquisition_channel TEXT NOT NULL
        CHECK (acquisition_channel IN (
            'organic', 'paid_search', 'referral',
            'partner', 'outbound'
        )),

    employee_band SMALLINT NOT NULL
        CHECK (employee_band > 0)
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,

    account_id BIGINT NOT NULL REFERENCES accounts (account_id),

    created_at TIMESTAMPTZ NOT NULL,

    role TEXT NOT NULL
        CHECK (LENGTH(TRIM(role)) > 0),

    is_admin BOOLEAN NOT NULL DEFAULT FALSE,

    deleted_at TIMESTAMPTZ,

    CONSTRAINT uq_users_user_account
    UNIQUE (user_id, account_id)
);

CREATE TABLE IF NOT EXISTS plans (
    plan_id SMALLINT PRIMARY KEY,

    plan_name TEXT NOT NULL UNIQUE
        CHECK (LENGTH(TRIM(plan_name)) > 0),

    monthly_price_per_seat_cents INTEGER NOT NULL
        CHECK (monthly_price_per_seat_cents >= 0)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id BIGINT PRIMARY KEY,

    account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),

    plan_id SMALLINT NOT NULL
        REFERENCES plans(plan_id),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,

    seat_count INTEGER NOT NULL
        CHECK (seat_count > 0),

    billing_interval TEXT NOT NULL
        CHECK (billing_interval IN ('monthly', 'annual')),

    mrr_cents INTEGER NOT NULL
        CHECK (mrr_cents >= 0),

    cancel_reason TEXT,

    CONSTRAINT chk_subscription_dates
        CHECK (ended_at IS NULL OR ended_at > started_at),

    CONSTRAINT uq_subscriptions_subscription_account
        UNIQUE (subscription_id, account_id),

    CONSTRAINT no_overlapping_subscriptions
        EXCLUDE USING gist (
            account_id WITH =,
            tstzrange(started_at, ended_at, '[)') WITH &&
        )
);

CREATE TABLE IF NOT EXISTS events (
    event_id BIGINT PRIMARY KEY,

    user_id BIGINT
        REFERENCES users (user_id),

    account_id BIGINT NOT NULL
        REFERENCES accounts (account_id),

    event_name TEXT NOT NULL
        CHECK (LENGTH(TRIM(event_name)) > 0),

    event_time TIMESTAMPTZ NOT NULL,

    ingested_at TIMESTAMPTZ NOT NULL,

    properties JSONB NOT NULL DEFAULT '{}'::jsonb,

    CONSTRAINT fk_events_user_account
        FOREIGN KEY (user_id, account_id)
        REFERENCES users (user_id, account_id)

);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id BIGINT PRIMARY KEY,

    account_id BIGINT NOT NULL
        REFERENCES accounts(account_id),

    subscription_id BIGINT NOT NULL
        REFERENCES subscriptions(subscription_id),

    invoice_date DATE NOT NULL,

    amount_cents INTEGER NOT NULL,

    status TEXT NOT NULL
        CHECK (status IN ('paid', 'failed', 'pending', 'refunded')),

    paid_at TIMESTAMPTZ,

    CONSTRAINT chk_invoice_amount
        CHECK (amount_cents >= 0 OR status = 'refunded'),

    CONSTRAINT fk_invoices_subscription_account
        FOREIGN KEY (subscription_id, account_id)
        REFERENCES subscriptions (subscription_id, account_id)
);
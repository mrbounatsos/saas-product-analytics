
-- FlowDesk: Load core synthetic datasets
-- Run using psql from the project root.
-- Event files are loaded separately.

\set ON_ERROR_STOP on

\echo 'Loading plans...'
\copy plans (plan_id, plan_name, monthly_price_per_seat_cents) FROM 'data/raw/plans.csv' WITH (FORMAT csv, HEADER true)

\echo 'Loading accounts...'
\copy accounts (account_id, created_at, company_name, segment, country, acquisition_channel, employee_band) FROM 'data/raw/accounts.csv' WITH (FORMAT csv, HEADER true)

\echo 'Loading users...'
\copy users (user_id, account_id, created_at, role, is_admin, deleted_at) FROM 'data/raw/users.csv' WITH (FORMAT csv, HEADER true)

\echo 'Loading subscriptions...'
\copy subscriptions (subscription_id, account_id, plan_id, started_at, ended_at, seat_count, billing_interval, mrr_cents, cancel_reason) FROM 'data/raw/subscriptions.csv' WITH (FORMAT csv, HEADER true)

\echo 'Loading invoices...'
\copy invoices (invoice_id, account_id, subscription_id, invoice_date, amount_cents, status, paid_at) FROM 'data/raw/invoices.csv' WITH (FORMAT csv, HEADER true)

\echo 'Core data loading complete.'

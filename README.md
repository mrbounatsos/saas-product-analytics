# FlowDesk — Synthetic SaaS Analytics in PostgreSQL

**A reproducible, locally hosted data science project exploring the customer lifecycle of a fictional B2B SaaS platform.**

> **Project status:** In development. The PostgreSQL schema, integrity tests, local Docker environment, Python environment, and initial signup-probability function are implemented. The full synthetic dataset, downstream analyses, and dashboard are not yet complete.

## Overview

FlowDesk is a fictional team-collaboration SaaS product. The project simulates a business that acquires trial accounts but needs better evidence about onboarding, conversion, retention, recurring revenue, and churn. The goal is to build a reproducible analytics environment and use SQL, Python, and statistical methods to investigate customer behavior and inform decisions.

**All customers, events, prices, and results are synthetic.** This is a portfolio and engineering exercise, not an analysis of a real company. Observed associations in simulated data should not be presented as causal findings.

### Questions this project is designed to answer

1. Where do trial accounts drop out of onboarding?
2. Which early product behaviors are associated with conversion to paid plans?
3. Which account segments retain best over time?
4. How do new business, expansion, contraction, and churn affect monthly recurring revenue (MRR)?
5. Which changes in usage or billing may serve as early churn signals?

## Technology stack

| Component | Technology | Purpose |
|---|---|---|
| Database | PostgreSQL 16 (Docker) | Relational storage, constraints, SQL analytics |
| Development | Windows + WSL2, VS Code | Local development environment |
| Orchestration | Docker Compose | Reproducible local database service |
| Python tooling | Python 3.12, `uv` | Virtual environment and dependency locking |
| Data generation | NumPy, pandas, Faker, PyYAML, PyArrow | Synthetic accounts and future behavioral datasets |
| Testing | `pytest`, PostgreSQL SQL tests | Unit and database integrity tests |
| Visualization (planned) | Metabase | Product and revenue dashboard |

No AWS or GCP account is required.

## Current implementation

- **Six core tables:** `accounts`, `users`, `plans`, `subscriptions`, `events`, and `invoices`.
- **Referential integrity:** primary and foreign keys; composite foreign keys verify that an event's user belongs to its account and that an invoice's subscription belongs to its account.
- **Subscription timeline integrity:** a GiST exclusion constraint (using the `btree_gist` extension) prevents overlapping subscription periods for the same account.
- **SQL negative tests:** tests verify that invalid overlaps and account mismatches are rejected.
- **Python foundation:** a vectorized function calculates monthly signup probabilities under an assumed monthly growth rate, with `pytest` coverage.

### Planned synthetic data scale

| Dataset | Target volume |
|---|---:|
| Accounts | ~10,000 |
| Users | ~55,000 |
| Subscription episodes | ~18,000 |
| Product events | ~4 million |
| Invoices | ~150,000 |

The planned observation period is **2024-11-01 through 2026-10-31**. These are design targets, not data volumes already generated.

## Repository layout

```text
saas-product-analytics/
├── config/
│   └── generation.yaml
├── generator/
│   ├── __init__.py
│   └── generate_accounts.py
├── sql/
│   └── 00_schema.sql
├── tests/
│   ├── sql/
│   │   ├── test_subscription_overlap.sql
│   │   ├── test_event_account_fk.sql
│   │   └── test_invoice_subscription_fk.sql
│   └── test_generator.py
├── docker-compose.yml
├── .env.example
├── .python-version
├── pyproject.toml
├── uv.lock
└── README.md
```

Additional loading, quality-check, analytical, and dashboard files will be added as they are implemented.

## Local setup

### Prerequisites

- Docker Desktop with WSL2 integration (or a compatible Docker Engine + Compose setup)
- Python tooling: [`uv`](https://docs.astral.sh/uv/)
- Git and VS Code (recommended)

The documented commands below assume a WSL2/Linux terminal with Docker access and are run from the repository root.

### 1. Configure the database

```bash
cp .env.example .env
```

Edit `.env` and set a strong local password for `POSTGRES_PASSWORD`. **Never commit `.env` or real credentials.**

```bash
docker compose up -d
docker compose ps
```

The `flowdesk_postgres` container should become healthy. Database data is persisted in a Docker-managed volume. **Do not use `docker compose down -v` unless you intentionally want to delete the database volume.**

### 2. Apply the schema

For a new, empty database initialized by the Compose configuration:

```bash
docker exec -i flowdesk_postgres \
  psql -X -v ON_ERROR_STOP=1 -U flowdesk -d flowdesk_analytics \
  < sql/00_schema.sql
```

This creates the six core tables and their constraints. The schema uses `CREATE EXTENSION IF NOT EXISTS btree_gist`; the database role needs permission to create that extension.

To inspect the tables:

```bash
docker exec flowdesk_postgres \
  psql -U flowdesk -d flowdesk_analytics -c '\dt'
```

> **Note:** `CREATE TABLE IF NOT EXISTS` is not a migration mechanism. Re-running this file does not update existing table definitions.

### 3. Install Python dependencies

```bash
uv sync
uv run python --version
uv run pytest -v
```

`uv` uses the committed `pyproject.toml` and `uv.lock` and manages a local `.venv` directory.

## Database integrity testing

To run SQL tests independently of the main development database, first create a **fresh** test database:

```bash
docker exec flowdesk_postgres \
  psql -U flowdesk -d postgres -c 'CREATE DATABASE flowdesk_schema_test;'

docker exec -i flowdesk_postgres \
  psql -X -v ON_ERROR_STOP=1 -U flowdesk -d flowdesk_schema_test \
  < sql/00_schema.sql
```

Then run the negative integrity tests:

```bash
for test in tests/sql/test_*.sql; do
  echo "Running $test"
  docker exec -i flowdesk_postgres \
    psql -X -v ON_ERROR_STOP=1 -U flowdesk -d flowdesk_schema_test \
    < "$test" || exit 1
done
```

The tests are intended to **pass when the targeted invalid insert is rejected**, and to clean up their setup records with transaction rollback. The SQL files are currently run manually or using the shell loop above; a dedicated automated test runner is a future improvement.

## Metrics and modeling conventions

These definitions guide future analysis; their analytical SQL implementations are not yet complete.

| Metric | Intended definition |
|---|---|
| 14-day activation | Account creates a project, sends an invitation, and has a teammate join within 14 days of signup |
| Trial-to-paid conversion | Account starts a paid subscription within the first 14 days; evaluate only sufficiently mature signup cohorts |
| Logo churn | Paid subscription ends with no new paid subscription beginning within the following 30 days |
| MRR | Recurring contractual subscription value normalized to a monthly basis, not cash collected from invoices |

Financial amounts are stored as integer cents to avoid floating-point rounding issues in monetary aggregates. Cohort analyses must account for incomplete observation windows; churn-related features must be computed using only information available at their reference dates.

## Roadmap

- [x] Set up PostgreSQL locally with Docker Compose and persistent storage
- [x] Design and validate the relational schema
- [x] Add SQL integrity tests for overlaps and composite foreign keys
- [x] Configure `uv`, dependency locking, and initial Python unit tests
- [x] Implement monthly signup probability calculation
- [ ] Generate and validate synthetic account attributes and signup dates
- [ ] Generate users, subscription lifecycles, product events, and invoices
- [ ] Load synthetic data into PostgreSQL and add data-quality checks
- [ ] Implement activation, conversion, retention, MRR, and churn analyses
- [ ] Develop a reproducible dashboard and business findings
- [ ] Explore statistical relationships and optional churn modeling

## Reproducibility and limitations

The planned generator will use an explicit random seed and pinned Python dependencies. Its parameters will be kept in `config/generation.yaml`. Synthetic distributions and behavior rules are assumptions for simulation—not empirically validated SaaS benchmarks. Generated bulk data should not be committed to Git; scripts, configuration, small samples, tests, and documentation should be.

This README describes the implementation at its current stage. Analytical results and performance claims will be documented only after they have been produced and validated.


import numpy as np
import pandas as pd
from faker import Faker
from pathlib import Path


SEED = 20261106
N_ACCOUNTS = 10_000
N_MONTHS = 24
GROWTH_RATE = 0.02
START_DATE = "2024-11-01"


def monthly_signup_probabilities(
    n_months: int,
    growth_rate: float
) -> np.ndarray:
    month_indices = np.arange(n_months)
    weights = (1 + growth_rate) ** month_indices
    return weights / weights.sum()


def generate_signup_months(
    n_accounts: int,
    n_months: int,
    growth_rate: float,
    rng: np.random.Generator
) -> np.ndarray:
    probabilities = monthly_signup_probabilities(
        n_months, growth_rate
    )
    return rng.choice(
        a=n_months,
        size=n_accounts,
        p=probabilities
    )


def generate_signup_timestamps(
    signup_months: np.ndarray,
    start_date: str,
    rng: np.random.Generator
) -> np.ndarray:
    timestamps = []

    for month_index in signup_months:
        month_start = (
            pd.Timestamp(start_date)
            + pd.DateOffset(months=int(month_index))
        )
        month_end = month_start + pd.DateOffset(months=1)

        duration_seconds = (
            month_end - month_start
        ).total_seconds()

        random_seconds = rng.uniform(0, duration_seconds)

        timestamp = month_start + pd.Timedelta(
            seconds=random_seconds
        )
        timestamps.append(timestamp)

    return np.array(timestamps, dtype="datetime64[ns]")


def generate_account_segments(
    n_accounts: int,
    rng: np.random.Generator
) -> np.ndarray:
    return rng.choice(
        ["smb", "mid_market", "enterprise"],
        size=n_accounts,
        p=[0.65, 0.28, 0.07]
    )


def generate_acquisition_channels(
    n_accounts: int,
    rng: np.random.Generator
) -> np.ndarray:
    return rng.choice(
        ["organic", "paid_search", "referral", "partner", "outbound"],
        size=n_accounts,
        p=[0.30, 0.25, 0.20, 0.15, 0.10]
    )


def generate_employee_bands(
    segments: np.ndarray,
    rng: np.random.Generator
) -> np.ndarray:
    employees = np.empty(len(segments), dtype=np.int32)

    parameters = {
        "smb": (12, 2, 49),
        "mid_market": (120, 50, 499),
        "enterprise": (900, 500, 5000)
    }

    for segment, (median, lower, upper) in parameters.items():
        mask = segments == segment
        count = mask.sum()

        values = rng.lognormal(
            mean=np.log(median),
            sigma=0.6,
            size=count
        )

        employees[mask] = np.clip(
            np.rint(values), lower, upper
        ).astype(np.int32)

    return employees


def generate_accounts(
    n_accounts: int,
    rng: np.random.Generator,
    fake: Faker
) -> pd.DataFrame:

    signup_months = generate_signup_months(
        n_accounts, N_MONTHS, GROWTH_RATE, rng
    )

    timestamps = generate_signup_timestamps(
        signup_months, START_DATE, rng
    )

    segments = generate_account_segments(n_accounts, rng)
    channels = generate_acquisition_channels(n_accounts, rng)
    employees = generate_employee_bands(segments, rng)

    company_names = [
        fake.company() for _ in range(n_accounts)
    ]

    countries = rng.choice(
        ["US", "GB", "DE", "FR", "NL", "CA", "AU"],
        size=n_accounts,
        p=[0.40, 0.15, 0.12, 0.10, 0.08, 0.08, 0.07]
    )

    accounts = pd.DataFrame({
        "account_id": np.arange(1, n_accounts + 1),
        "created_at": pd.to_datetime(timestamps, utc=True),
        "company_name": company_names,
        "segment": segments,
        "country": countries,
        "acquisition_channel": channels,
        "employee_band": employees
    })

    return accounts


def main():
    rng = np.random.default_rng(SEED)
    fake = Faker("en_US")
    fake.seed_instance(SEED)

    accounts = generate_accounts(
        n_accounts=N_ACCOUNTS,
        rng=rng,
        fake=fake
    )

    output_dir = Path("data/raw")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "accounts.csv"
    accounts.to_csv(output_path, index=False)

    print(f"Generated {len(accounts):,} accounts")
    print(f"Saved to: {output_path}")

    print("\nSegment distribution:")
    print(accounts["segment"].value_counts(normalize=True))

    print("\nSignup date range:")
    print(accounts["created_at"].min())
    print(accounts["created_at"].max())

    print("\nFirst five records:")
    print(accounts.head())


if __name__ == "__main__":
    main()

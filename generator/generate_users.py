
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------
# Configuration
# --------------------------------------------------

SEED = 20261107
TARGET_USERS = 55_000
END_DATE = pd.Timestamp("2026-11-01", tz="UTC")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "raw"


# --------------------------------------------------
# Allocate users to accounts
# --------------------------------------------------

def generate_user_counts(
    accounts: pd.DataFrame,
    target_users: int,
    rng: np.random.Generator
) -> np.ndarray:

    n_accounts = len(accounts)

    if target_users < n_accounts:
        raise ValueError(
            "Target users must be >= number of accounts."
        )

    employees = accounts["employee_band"].to_numpy(
        dtype=np.int64
    )

    if np.any(employees < 1):
        raise ValueError("Employee counts must be positive.")

    if target_users > employees.sum():
        raise ValueError(
            "Not enough employee capacity for target users."
        )

    # Every account starts with one user.
    counts = np.ones(n_accounts, dtype=np.int64)

    # Remaining available seats per account.
    capacity = employees - 1

    remaining = target_users - n_accounts

    # Larger companies generally have more users,
    # but the relationship is sublinear.
    weights = np.sqrt(employees.astype(float))

    # Random variation between accounts.
    noise = rng.lognormal(
        mean=0.0,
        sigma=0.4,
        size=n_accounts
    )

    weights *= noise

    # Distribute remaining users without exceeding
    # employee capacity.
    while remaining > 0:

        eligible = capacity > 0

        probabilities = np.where(
            eligible,
            weights,
            0.0
        )
        probabilities /= probabilities.sum()

        allocations = rng.multinomial(
            remaining,
            probabilities
        )

        allocations = np.minimum(
            allocations,
            capacity
        )

        assigned = int(allocations.sum())

        if assigned == 0:
            # Very rare fallback when the remaining
            # allocation is heavily concentrated.
            available = np.flatnonzero(eligible)
            selected = rng.choice(available)
            allocations[selected] = 1
            assigned = 1

        counts += allocations
        capacity -= allocations
        remaining -= assigned

    return counts


# --------------------------------------------------
# Generate users
# --------------------------------------------------

def generate_users(
    accounts: pd.DataFrame,
    target_users: int,
    rng: np.random.Generator
) -> pd.DataFrame:

    counts = generate_user_counts(
        accounts,
        target_users,
        rng
    )

    records = []
    user_id = 1

    for account, n_users in zip(
        accounts.itertuples(index=False),
        counts
    ):

        account_id = account.account_id
        account_created = pd.Timestamp(account.created_at)

        # Other users can join after account creation.
        available_seconds = (
            END_DATE - account_created
        ).total_seconds()

        for user_index in range(int(n_users)):

            if user_index == 0:
                # Every account has an original owner.
                created_at = account_created
                role = "owner"
                is_admin = True

            else:
                # Bias joining toward earlier account life.
                join_fraction = rng.beta(0.9, 3.0)

                join_seconds = (
                    join_fraction * available_seconds
                )

                created_at = (
                    account_created
                    + pd.Timedelta(seconds=join_seconds)
                )

                is_admin = bool(rng.random() < 0.08)

                role = "admin" if is_admin else "member"

            # Some users are eventually deleted.
            # Owners remain active in this version.
            deleted_at = pd.NaT

            if user_index > 0 and rng.random() < 0.03:

                lifetime_seconds = (
                    END_DATE - created_at
                ).total_seconds()

                deletion_fraction = rng.uniform(0.05, 1.0)

                deleted_at = (
                    created_at
                    + pd.Timedelta(
                        seconds=deletion_fraction
                        * lifetime_seconds
                    )
                )

            records.append({
                "user_id": user_id,
                "account_id": account_id,
                "created_at": created_at,
                "role": role,
                "is_admin": is_admin,
                "deleted_at": deleted_at
            })

            user_id += 1

    users = pd.DataFrame.from_records(records)

    users["created_at"] = pd.to_datetime(
        users["created_at"],
        utc=True
    )

    users["deleted_at"] = pd.to_datetime(
        users["deleted_at"],
        utc=True
    )

    return users


# --------------------------------------------------
# Validate generated users
# --------------------------------------------------

def validate_users(
    accounts: pd.DataFrame,
    users: pd.DataFrame,
    target_users: int
) -> None:

    assert len(users) == target_users, (
        "Incorrect total user count."
    )

    assert users["user_id"].is_unique, (
        "Duplicate user IDs."
    )

    assert users["account_id"].isin(
        accounts["account_id"]
    ).all(), "Invalid account references."

    user_counts = users.groupby(
        "account_id"
    ).size()

    assert len(user_counts) == len(accounts), (
        "Some accounts have no users."
    )

    assert user_counts.min() >= 1

    merged = users.merge(
        accounts[["account_id", "created_at"]],
        on="account_id",
        suffixes=("_user", "_account"),
        validate="many_to_one"
    )

    assert (
        merged["created_at_user"]
        >= merged["created_at_account"]
    ).all(), "User created before account."

    assert (
        users["created_at"] < END_DATE
    ).all(), "User created after cutoff."

    deleted = users["deleted_at"].notna()

    assert (
        users.loc[deleted, "deleted_at"]
        > users.loc[deleted, "created_at"]
    ).all(), "Invalid deletion timestamps."

    assert (
        users.loc[deleted, "deleted_at"] < END_DATE
    ).all(), "Deletion after cutoff."

    employee_capacity = accounts.set_index(
        "account_id"
    )["employee_band"]

    assert (
        user_counts <= employee_capacity.loc[
            user_counts.index
        ]
    ).all(), "Users exceed employee counts."

    owners = users[users["role"] == "owner"]

    assert (
        owners.groupby("account_id").size() == 1
    ).all() and len(owners) == len(accounts), (
        "Each account must have exactly one owner."
    )

    print("All user validation checks passed.")


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():

    rng = np.random.default_rng(SEED)

    accounts_path = DATA_DIR / "accounts.csv"

    accounts = pd.read_csv(
        accounts_path,
        parse_dates=["created_at"]
    )

    accounts["created_at"] = pd.to_datetime(
        accounts["created_at"],
        utc=True
    )

    users = generate_users(
        accounts=accounts,
        target_users=TARGET_USERS,
        rng=rng
    )

    validate_users(
        accounts,
        users,
        TARGET_USERS
    )

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    output_path = DATA_DIR / "users.csv"

    users.to_csv(output_path, index=False)

    print(f"\nGenerated {len(users):,} users")
    print(f"Saved to: {output_path}")

    print("\nRole distribution:")
    print(users["role"].value_counts())

    print("\nUsers per account:")
    print(
        users.groupby("account_id")
        .size()
        .describe()
    )

    print("\nUsers by segment:")
    print(
        users.merge(
            accounts[["account_id", "segment"]],
            on="account_id"
        )
        .groupby("segment")
        .size()
    )

    print("\nFirst five records:")
    print(users.head())


if __name__ == "__main__":
    main()

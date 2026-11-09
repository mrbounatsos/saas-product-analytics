"""Generate FlowDesk plans, subscription episodes, and latent account traits.

Run from repository root:
    uv run python generator/generate_subscriptions.py

Input: data/raw/accounts.csv, data/raw/users.csv
Output: data/raw/plans.csv, data/raw/subscriptions.csv,
        data/raw/account_traits.csv

Synthetic monthly decisions, NOT industry-calibrated subscription benchmarks.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261108
CUTOFF = pd.Timestamp("2026-11-01", tz="UTC")  # exclusive
TRIAL_DAYS = 14
ANNUAL_DISCOUNT = 0.10
REACTIVATION_PROBABILITY = 0.20

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

PLAN_PRICES_CENTS = {1: 0, 2: 1200, 3: 2400, 4: 4000}


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def generate_plans() -> pd.DataFrame:
    return pd.DataFrame({
        "plan_id": [1, 2, 3, 4],
        "plan_name": ["Trial", "Starter", "Pro", "Business"],
        "monthly_price_per_seat_cents": [0, 1200, 2400, 4000],
    })


def calculate_mrr(plan_id: int, seats: int, billing_interval: str) -> int:
    price = PLAN_PRICES_CENTS[plan_id]
    factor = 1.0 - ANNUAL_DISCOUNT if billing_interval == "annual" else 1.0
    return round(price * seats * factor)


def generate_account_traits(accounts: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    n = len(accounts)
    return pd.DataFrame({
        "account_id": accounts["account_id"].to_numpy(),
        "product_fit": rng.beta(2.5, 2.0, n),
        "collaboration": rng.beta(2.0, 2.5, n),
        "price_sensitivity": rng.beta(2.0, 2.0, n),
        "engagement": rng.beta(2.5, 2.0, n),
    })


def conversion_probability(account, traits) -> float:
    segment_effect = {"smb": -0.20, "mid_market": 0.10, "enterprise": 0.25}
    channel_effect = {
        "organic": 0.05,
        "paid_search": -0.10,
        "referral": 0.25,
        "partner": 0.15,
        "outbound": -0.05,
    }
    return sigmoid(
        -1.0
        + 1.4 * traits.product_fit
        + 0.7 * traits.collaboration
        + 0.4 * traits.engagement
        - 0.8 * traits.price_sensitivity
        + segment_effect[account.segment]
        + channel_effect[account.acquisition_channel]
    )


def choose_initial_plan(segment: str, rng: np.random.Generator) -> int:
    probabilities = {
        "smb": [0.85, 0.14, 0.01],
        "mid_market": [0.35, 0.55, 0.10],
        "enterprise": [0.10, 0.35, 0.55],
    }
    return int(rng.choice([2, 3, 4], p=probabilities[segment]))


def choose_interval(rng: np.random.Generator) -> str:
    return str(rng.choice(["monthly", "annual"], p=[0.75, 0.25]))


def current_user_count(account_users: pd.DataFrame, at: pd.Timestamp) -> int:
    active = (account_users["created_at"] <= at) & (
        account_users["deleted_at"].isna() | (account_users["deleted_at"] > at)
    )
    return max(1, int(active.sum()))


def monthly_churn_probability(traits, interval: str) -> float:
    # Approximately low-single-digit monthly hazard, varying by account traits.
    # No future usage information is used in the churn decision.
    logit = (
        -2.9
        - 0.8 * traits.collaboration
        - 0.6 * traits.engagement
        - 0.3 * traits.product_fit
        + 0.7 * traits.price_sensitivity
    )
    probability = sigmoid(logit)
    return probability * (0.6 if interval == "annual" else 1.0)


def choose_change(
    plan_id: int, seats: int, employee_capacity: int,
    rng: np.random.Generator,
) -> tuple[int, int]:
    """Return a genuine plan or seat change; otherwise keep the current state."""
    possibilities = []
    if plan_id < 4:
        possibilities.append("upgrade")
    if plan_id > 2:
        possibilities.append("downgrade")
    if seats < employee_capacity:
        possibilities.append("add_seats")
    if seats > 1:
        possibilities.append("remove_seats")
    if not possibilities:
        return plan_id, seats

    action = str(rng.choice(possibilities))
    if action == "upgrade":
        return plan_id + 1, seats
    if action == "downgrade":
        return plan_id - 1, seats
    if action == "add_seats":
        return plan_id, min(employee_capacity, seats + int(rng.integers(1, 3)))
    return plan_id, max(1, seats - int(rng.integers(1, 3)))


def generate_subscriptions(
    accounts: pd.DataFrame,
    users: pd.DataFrame,
    traits: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    next_id = 1
    traits_lookup = {int(x.account_id): x for x in traits.itertuples(index=False)}
    users_by_account = {
        int(account_id): group
        for account_id, group in users.groupby("account_id", sort=False)
    }

    def append_episode(account_id, plan_id, start, end, seats, interval, reason=None):
        nonlocal next_id
        if end is not None and end <= start:
            raise ValueError(f"Non-positive subscription duration: account {account_id}")
        rows.append({
            "subscription_id": next_id,
            "account_id": int(account_id),
            "plan_id": int(plan_id),
            "started_at": start,
            "ended_at": end,
            "seat_count": int(seats),
            "billing_interval": interval,
            "mrr_cents": calculate_mrr(plan_id, seats, interval),
            "cancel_reason": reason,
        })
        next_id += 1

    for account in accounts.itertuples(index=False):
        account_id = int(account.account_id)
        signup = account.created_at
        trial_end = signup + pd.Timedelta(days=TRIAL_DAYS)

        append_episode(
            account_id, 1, signup,
            trial_end if trial_end < CUTOFF else None,
            1, "monthly",
        )
        if trial_end >= CUTOFF:
            continue  # right-censored trial

        traits_row = traits_lookup[account_id]
        if rng.random() >= conversion_probability(account, traits_row):
            continue

        start = trial_end + pd.Timedelta(days=int(rng.integers(0, 4)))
        if start >= CUTOFF:
            continue

        account_users = users_by_account[account_id]
        employee_capacity = int(account.employee_band)
        plan_id = choose_initial_plan(account.segment, rng)
        interval = choose_interval(rng)
        seats = min(employee_capacity, current_user_count(account_users, start))

        # One open subscription episode per paid period. Monthly decision
        # dates are fixed from each paid spell's start (not the last change).
        while start < CUTOFF:
            spell_start = start
            episode_start = start
            month_number = 1
            churned = False

            while True:
                decision_at = spell_start + pd.DateOffset(months=month_number)
                if decision_at >= CUTOFF:
                    append_episode(
                        account_id, plan_id, episode_start, None, seats, interval
                    )
                    break

                # Every month: independently evaluate churn AND plan changes.
                if rng.random() < monthly_churn_probability(traits_row, interval):
                    reason = str(rng.choice(
                        ["low_usage", "pricing", "missing_features", "business_closed"],
                        p=[0.40, 0.25, 0.25, 0.10],
                    ))
                    append_episode(
                        account_id, plan_id, episode_start, decision_at,
                        seats, interval, reason,
                    )
                    churned = True
                    start = decision_at
                    break

                # Decision frequency is synthetic, not industry-calibrated.
                if rng.random() < 0.08:
                    new_plan, new_seats = choose_change(
                        plan_id, seats, employee_capacity, rng
                    )
                    if (new_plan, new_seats) != (plan_id, seats):
                        append_episode(
                            account_id, plan_id, episode_start,
                            decision_at, seats, interval,
                        )
                        episode_start = decision_at
                        plan_id, seats = new_plan, new_seats

                month_number += 1

            if not churned:
                break  # active at cutoff; no extra paid spell

            if rng.random() >= REACTIVATION_PROBABILITY:
                break

            start = start + pd.Timedelta(days=int(rng.integers(31, 121)))
            if start >= CUTOFF:
                break

            # A reactivation is a new paid spell.
            plan_id = choose_initial_plan(account.segment, rng)
            interval = choose_interval(rng)
            seats = min(employee_capacity, current_user_count(account_users, start))

    result = pd.DataFrame(rows)
    for column in ("started_at", "ended_at"):
        result[column] = pd.to_datetime(result[column], utc=True)
    return result


def validate_subscriptions(accounts: pd.DataFrame, subs: pd.DataFrame) -> None:
    assert subs["subscription_id"].is_unique
    assert subs["account_id"].isin(accounts["account_id"]).all()
    assert subs["started_at"].notna().all()
    assert (subs["started_at"] < CUTOFF).all()
    ended = subs["ended_at"].notna()
    assert (subs.loc[ended, "ended_at"] > subs.loc[ended, "started_at"]).all()
    assert (subs.loc[ended, "ended_at"] <= CUTOFF).all()
    assert (subs["seat_count"] > 0).all()
    assert subs["billing_interval"].isin(["monthly", "annual"]).all()

    trials = subs[subs["plan_id"] == 1]
    paid = subs[subs["plan_id"] != 1]
    assert len(trials) == len(accounts) and trials["account_id"].is_unique
    assert (trials["mrr_cents"] == 0).all()
    assert (paid["mrr_cents"] > 0).all()
    assert paid["cancel_reason"].notna().sum() > 0

    calculated = subs.apply(
        lambda s: calculate_mrr(s.plan_id, s.seat_count, s.billing_interval),
        axis=1,
    )
    assert (subs["mrr_cents"].to_numpy() == calculated.to_numpy()).all()

    ordered = subs.sort_values(["account_id", "started_at", "subscription_id"])
    prior_end = ordered.groupby("account_id")["ended_at"].shift()
    has_prior = ordered.groupby("account_id").cumcount() > 0
    assert (~has_prior | (prior_end.notna() & (ordered["started_at"] >= prior_end))).all(), (
        "Overlapping subscription episodes"
    )
    print("All subscription validation checks passed.")


def main() -> None:
    rng = np.random.default_rng(SEED)
    accounts = pd.read_csv(DATA_DIR / "accounts.csv", parse_dates=["created_at"])
    users = pd.read_csv(DATA_DIR / "users.csv", parse_dates=["created_at", "deleted_at"])
    accounts["created_at"] = pd.to_datetime(accounts["created_at"], utc=True)
    for col in ("created_at", "deleted_at"):
        users[col] = pd.to_datetime(users[col], utc=True)

    plans = generate_plans()
    traits = generate_account_traits(accounts, rng)
    subscriptions = generate_subscriptions(accounts, users, traits, rng)
    validate_subscriptions(accounts, subscriptions)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    plans.to_csv(DATA_DIR / "plans.csv", index=False)
    traits.to_csv(DATA_DIR / "account_traits.csv", index=False)
    subscriptions.to_csv(DATA_DIR / "subscriptions.csv", index=False)

    paid = subscriptions[subscriptions["plan_id"] != 1]
    print(f"Subscription episodes: {len(subscriptions):,}")
    print(f"Paid episodes: {len(paid):,}")
    print(f"Unique paid accounts: {paid['account_id'].nunique():,}")
    print(f"Cancellation episodes: {paid['cancel_reason'].notna().sum():,}")
    print("Billing intervals:")
    print(paid["billing_interval"].value_counts(normalize=True).round(3))
    print("Cancellation reasons:")
    print(paid["cancel_reason"].value_counts())


if __name__ == "__main__":
    main()

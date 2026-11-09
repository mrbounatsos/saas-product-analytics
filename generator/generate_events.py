
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20261109
TARGET_EVENTS = 4_000_000
CUTOFF = pd.Timestamp("2026-11-01", tz="UTC")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
OUTPUT_DIR = DATA_DIR / "events"

EVENT_NAMES = np.array([
    "login",
    "task_created",
    "comment_created",
    "project_created",
    "invite_sent",
    "integration_connected",
    "report_viewed",
    "export_created",
])

BASE_WEIGHTS = np.array([
    0.30, 0.30, 0.16, 0.07,
    0.06, 0.03, 0.05, 0.03
])


def load_inputs():
    accounts = pd.read_csv(
        DATA_DIR / "accounts.csv",
        parse_dates=["created_at"]
    )

    users = pd.read_csv(
        DATA_DIR / "users.csv",
        parse_dates=["created_at", "deleted_at"]
    )

    subscriptions = pd.read_csv(
        DATA_DIR / "subscriptions.csv",
        parse_dates=["started_at", "ended_at"]
    )

    traits = pd.read_csv(
        DATA_DIR / "account_traits.csv"
    )

    for frame, columns in [
        (accounts, ["created_at"]),
        (users, ["created_at", "deleted_at"]),
        (subscriptions, ["started_at", "ended_at"]),
    ]:
        for column in columns:
            frame[column] = pd.to_datetime(
                frame[column], utc=True
            )

    return accounts, users, subscriptions, traits


def event_probabilities(traits):
    weights = BASE_WEIGHTS.copy()

    # Collaboration influences comments/invitations.
    weights[2] *= 0.5 + 1.5 * traits["collaboration"]
    weights[4] *= 0.5 + 1.5 * traits["collaboration"]

    # Product fit influences feature usage.
    weights[3] *= 0.5 + traits["product_fit"]
    weights[5] *= 0.5 + traits["product_fit"]

    # Engagement influences task creation.
    weights[1] *= 0.5 + traits["engagement"]

    return weights / weights.sum()


def generate_lifecycle_events(
    accounts, users, traits, dormant_ids, rng
):
    """
    Generate important onboarding events and
    actual teammate-joining events.
    """
    records = []

    trait_lookup = traits.set_index("account_id")

    user_groups = {
        account_id: group.sort_values("created_at")
        for account_id, group in users.groupby("account_id")
    }

    for account in accounts.itertuples(index=False):
        account_id = account.account_id

        if account_id in dormant_ids:
            continue

        signup = account.created_at
        owner = user_groups[account_id].iloc[0]
        owner_id = int(owner["user_id"])

        t = trait_lookup.loc[account_id]

        def emit(user_id, name, when):
            if when < CUTOFF:
                records.append({
                    "account_id": account_id,
                    "user_id": int(user_id),
                    "event_name": name,
                    "event_time": when,
                })

        emit(owner_id, "workspace_created", signup)

        # Joining events correspond to real user
        # creation timestamps, not invented joins.
        teammates = user_groups[account_id].iloc[1:]

        for teammate in teammates.itertuples(index=False):
            emit(
                teammate.user_id,
                "teammate_joined",
                teammate.created_at
            )

        # Generate onboarding steps probabilistically.
        p_project = min(
            0.95, 0.35 + 0.55 * t["product_fit"]
        )

        p_invite = min(
            0.95, 0.25 + 0.60 * t["collaboration"]
        )

        if rng.random() >= p_project:
            continue

        early_joiners = teammates[
            teammates["created_at"]
            < signup + pd.Timedelta(days=14)
        ]

        if len(early_joiners) > 0:
            first_join = early_joiners.iloc[0]["created_at"]

            # Create ordered actions before the join.
            duration = first_join - signup

            project_at = signup + duration * 0.25
            invite_at = signup + duration * 0.60

        else:
            project_at = signup + pd.Timedelta(
                hours=float(rng.uniform(1, 48))
            )

            invite_at = project_at + pd.Timedelta(
                hours=float(rng.uniform(1, 48))
            )

        emit(owner_id, "project_created", project_at)

        if rng.random() < p_invite:
            emit(owner_id, "invite_sent", invite_at)

    return pd.DataFrame.from_records(records)


def build_activity_spans(
    subscriptions, traits, dormant_ids
):
    """
    Construct event-generation intervals.

    Each interval belongs to one account and
    one calendar month. Activity is lower in
    the 28 days preceding a simulated cancellation.
    """
    trait_lookup = traits.set_index("account_id")
    spans = []

    for sub in subscriptions.itertuples(index=False):
        account_id = sub.account_id

        if account_id in dormant_ids:
            continue

        start = sub.started_at

        end = (
            sub.ended_at
            if pd.notna(sub.ended_at)
            else CUTOFF
        )

        end = min(end, CUTOFF)

        if start >= end:
            continue

        t = trait_lookup.loc[account_id]

        engagement = float(t["engagement"])
        collaboration = float(t["collaboration"])

        multiplier = (
            0.55 if sub.plan_id == 1 else 1.0
        )

        # Split into monthly intervals.
        cursor = start

        while cursor < end:
            next_month = (
                cursor.normalize().replace(day=1)
                + pd.DateOffset(months=1)
            )

            month_end = min(next_month, end)

            # Split pre-churn periods so the event
            # intensity can decline before churn.
            boundaries = [cursor, month_end]

            if pd.notna(sub.ended_at) and pd.notna(
                sub.cancel_reason
            ):
                decline_start = (
                    sub.ended_at
                    - pd.Timedelta(days=28)
                )

                if cursor < decline_start < month_end:
                    boundaries = [
                        cursor, decline_start, month_end
                    ]

            for left, right in zip(
                boundaries[:-1], boundaries[1:]
            ):
                duration_days = (
                    right - left
                ).total_seconds() / 86400

                intensity = (
                    duration_days
                    * (0.2 + engagement)
                    * (0.7 + collaboration)
                    * multiplier
                )

                if pd.notna(sub.ended_at) and pd.notna(
                    sub.cancel_reason
                ):
                    if left >= (
                        sub.ended_at
                        - pd.Timedelta(days=28)
                    ):
                        intensity *= 0.35

                spans.append({
                    "account_id": account_id,
                    "month": left.strftime("%Y-%m"),
                    "start": left,
                    "end": right,
                    "weight": intensity,
                })

            cursor = month_end

    return pd.DataFrame.from_records(spans)


def generate_month_events(
    month_spans,
    lifecycle_events,
    users_by_account,
    trait_lookup,
    rng,
):
    batches = []

    for span in month_spans.itertuples(index=False):
        n = int(span.event_count)

        if n == 0:
            continue

        start_ns = span.start.value
        duration_ns = span.end.value - start_ns

        offsets = rng.integers(
            0, duration_ns, size=n, dtype=np.int64
        )

        times_ns = start_ns + offsets
        times = pd.to_datetime(times_ns, utc=True)

        # Select only users who are valid for the
        # entire interval. The account owner is
        # available as a fallback.
        account_users = users_by_account[span.account_id]

        eligible = account_users[
            (account_users["created_at"] <= span.start)
            & (
                account_users["deleted_at"].isna()
                | (account_users["deleted_at"] >= span.end)
            )
        ]

        if eligible.empty:
            raise ValueError(
                f"No eligible user for account "
                f"{span.account_id}"
            )

        user_ids = rng.choice(
            eligible["user_id"].to_numpy(),
            size=n
        )

        probabilities = event_probabilities(
            trait_lookup.loc[span.account_id]
        )

        names = rng.choice(
            EVENT_NAMES,
            size=n,
            p=probabilities
        )

        batches.append(pd.DataFrame({
            "account_id": span.account_id,
            "user_id": user_ids,
            "event_name": names,
            "event_time": times,
        }))

    if not lifecycle_events.empty:
        batches.append(lifecycle_events.copy())

    if not batches:
        return pd.DataFrame(columns=[
            "account_id", "user_id",
            "event_name", "event_time"
        ])

    return pd.concat(batches, ignore_index=True)


def validate_event_batch(events, accounts, users):
    assert events["account_id"].isin(
        accounts["account_id"]
    ).all()

    assert events["user_id"].isin(
        users["user_id"]
    ).all()

    assert events["event_time"].notna().all()

    assert (
        events["event_time"] < CUTOFF
    ).all()

    assert events["event_name"].isin(
        list(EVENT_NAMES)
        + ["workspace_created", "teammate_joined"]
    ).all()


def main():
    rng = np.random.default_rng(SEED)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    accounts, users, subscriptions, traits = load_inputs()

    # Reserve 1% of accounts with no product events.
    dormant_ids = set(
        rng.choice(
            accounts["account_id"].to_numpy(),
            size=max(1, len(accounts) // 100),
            replace=False
        ).tolist()
    )

    lifecycle = generate_lifecycle_events(
        accounts, users, traits, dormant_ids, rng
    )

    spans = build_activity_spans(
        subscriptions, traits, dormant_ids
    )

    remaining = TARGET_EVENTS - len(lifecycle)

    if remaining < 0:
        raise ValueError(
            "Lifecycle events exceed target event count."
        )

    # Multinomial allocation ensures the total is
    # exactly TARGET_EVENTS.
    weights = spans["weight"].to_numpy(dtype=float, copy=True)

    if not np.isfinite(weights).all():
        raise ValueError("Activity weights contain invalid values.")

    if (weights < 0).any() or weights.sum() <= 0:
        raise ValueError("Activity weights must be nonnegative with a positive sum.")

    weights /= weights.sum()

    spans["event_count"] = rng.multinomial(
        remaining,
        weights
    )

    spans["event_count"] = rng.multinomial(
        remaining, weights
    )

    users_by_account = {
        account_id: group
        for account_id, group in users.groupby("account_id")
    }

    trait_lookup = traits.set_index("account_id")

    next_event_id = 1
    total_written = 0

    months = pd.period_range(
        "2024-11", "2026-10", freq="M"
    )

    for month in months:
        month_label = str(month)

        month_spans = spans[
            spans["month"] == month_label
        ]

        month_lifecycle = lifecycle[
            lifecycle["event_time"]
            .dt.strftime("%Y-%m") == month_label
        ]

        events = generate_month_events(
            month_spans,
            month_lifecycle,
            users_by_account,
            trait_lookup,
            rng
        )

        events = events.sort_values(
            "event_time"
        ).reset_index(drop=True)

        n = len(events)

        events.insert(
            0,
            "event_id",
            np.arange(
                next_event_id,
                next_event_id + n,
                dtype=np.int64
            )
        )

        next_event_id += n

        # Simulate ingestion delays of 0 to 72 hours.
        delays = rng.integers(
            0, 72 * 3600 + 1, size=n
        )

        events["ingested_at"] = (
            events["event_time"]
            + pd.to_timedelta(delays, unit="s")
        )

        # PostgreSQL-compatible JSONB text.
        events["properties"] = "{}"

        validate_event_batch(
            events, accounts, users
        )

        output_path = (
            OUTPUT_DIR / f"{month_label}.csv.gz"
        )

        events.to_csv(
            output_path,
            index=False,
            compression="gzip"
        )

        total_written += n

        print(
            f"{month_label}: {n:,} events"
        )

    assert total_written == TARGET_EVENTS

    print("\nGeneration complete.")
    print(f"Total events: {total_written:,}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

"""Effective-dated subscription episode consistency."""
import numpy as np
import pandas as pd
from conftest import START, CUTOFF


def test_primary_and_foreign_keys(subscriptions, accounts, plans):
    s = subscriptions
    assert s.subscription_id.notna().all() and s.subscription_id.is_unique
    assert s.account_id.isin(accounts.account_id).all()
    assert s.plan_id.isin(plans.plan_id).all()


def test_subscription_boundaries(subscriptions):
    s = subscriptions
    assert s.started_at.notna().all()
    assert s.started_at.ge(START).all() and s.started_at.lt(CUTOFF).all()
    assert (s.ended_at.isna() | s.ended_at.gt(s.started_at)).all()
    assert s.ended_at.dropna().le(CUTOFF).all()
    assert s.seat_count.gt(0).all()
    assert s.billing_interval.isin({"monthly", "annual"}).all()


def test_no_overlapping_episodes(subscriptions):
    s = subscriptions.sort_values(["account_id", "started_at", "subscription_id"])
    prior_end = s.groupby("account_id").ended_at.shift()
    after_first = s.groupby("account_id").cumcount().gt(0)
    assert (~after_first | (prior_end.notna() & s.started_at.ge(prior_end))).all()


def test_trial_coverage_and_paid_start(subscriptions, accounts):
    s = subscriptions
    trials = s[s.plan_id.eq(1)]
    assert len(trials) == len(accounts) and trials.account_id.is_unique
    assert trials.mrr_cents.eq(0).all()
    first_paid = s[s.plan_id.ne(1)].groupby("account_id").started_at.min()
    trial_end = trials.set_index("account_id").started_at + pd.Timedelta(days=14)
    assert first_paid.ge(trial_end.reindex(first_paid.index)).all()


def test_mrr_contract_math(subscriptions, plans):
    s = subscriptions
    price = s.plan_id.map(plans.set_index("plan_id").monthly_price_per_seat_cents)
    assert price.notna().all()
    expected = np.rint(price.to_numpy() * s.seat_count.to_numpy() * np.where(s.billing_interval.eq("annual"), 0.9, 1.0)).astype(np.int64)
    assert np.array_equal(s.mrr_cents.to_numpy(), expected)
    assert s.loc[s.plan_id.ne(1), "mrr_cents"].gt(0).all()

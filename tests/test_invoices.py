"""Invoice references, status semantics, and basic billing consistency."""
import pandas as pd
from conftest import CUTOFF


def test_keys_and_references(invoices, subscriptions, accounts):
    assert invoices.invoice_id.notna().all() and invoices.invoice_id.is_unique
    assert invoices.account_id.isin(accounts.account_id).all()
    assert invoices.subscription_id.isin(subscriptions.subscription_id).all()
    merged = invoices.merge(subscriptions[["subscription_id", "account_id", "plan_id"]], on="subscription_id", suffixes=("_invoice", "_subscription"), validate="many_to_one")
    assert merged.account_id_invoice.eq(merged.account_id_subscription).all()
    assert merged.plan_id.ne(1).all()


def test_invoice_status_amounts_and_dates(invoices):
    i = invoices
    assert i.invoice_date.notna().all()
    assert i.invoice_date.lt(CUTOFF.tz_localize(None)).all()
    assert i.status.isin({"paid", "failed", "refunded"}).all()
    assert i.loc[i.status.ne("refunded"), "amount_cents"].gt(0).all()
    assert i.loc[i.status.eq("refunded"), "amount_cents"].lt(0).all()
    assert i.loc[i.status.eq("failed"), "paid_at"].isna().all()
    assert i.loc[i.status.isin({"paid", "refunded"}), "paid_at"].notna().all()
    assert i.paid_at.dropna().lt(CUTOFF).all()


def test_invoice_dates_within_subscriptions(invoices, subscriptions):
    i = invoices.merge(subscriptions[["subscription_id", "started_at", "ended_at"]], on="subscription_id", validate="many_to_one")
    # Date-only invoices cannot be compared to precise start time directly.
    assert i.invoice_date.ge(i.started_at.dt.tz_localize(None).dt.normalize()).all()
    # Refunds may legitimately be issued after the subscription episode ended.
    regular = i[i.status.ne("refunded")]
    end = regular.ended_at.dt.tz_localize(None).dt.normalize()
    assert (end.isna() | regular.invoice_date.le(end)).all()

"""Optional descriptive report (not part of pytest's strict acceptance suite)."""
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "raw"


def main():
    accounts = pd.read_csv(DATA / "accounts.csv")
    subscriptions = pd.read_csv(DATA / "subscriptions.csv")
    invoices = pd.read_csv(DATA / "invoices.csv")
    paid = subscriptions[subscriptions.plan_id.ne(1)]
    print(f"Accounts: {len(accounts):,}")
    print(f"Paid accounts: {paid.account_id.nunique():,}")
    print(f"Observed ever-paid fraction: {paid.account_id.nunique()/len(accounts):.1%}")
    print(f"Paid episodes: {len(paid):,}")
    print(f"Cancellation episodes: {paid.cancel_reason.notna().sum():,}")
    print(f"Invoices: {len(invoices):,}")
    print("Billing intervals:")
    print(paid.billing_interval.value_counts(normalize=True))


if __name__ == "__main__":
    main()

"""Shared fixtures for generated FlowDesk CSVs."""
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw"
START = pd.Timestamp("2024-11-01", tz="UTC")
CUTOFF = pd.Timestamp("2026-11-01", tz="UTC")
CHUNK_SIZE = 150_000
EVENT_NAMES = {
    "workspace_created", "project_created", "task_created", "invite_sent",
    "teammate_joined", "comment_created", "integration_connected",
    "report_viewed", "export_created", "login",
}


def to_utc(series):
    return pd.to_datetime(series, utc=True, errors="coerce")


@pytest.fixture(scope="session")
def data_dir():
    assert DATA.is_dir(), f"Missing data directory: {DATA}"
    return DATA


@pytest.fixture(scope="session")
def accounts(data_dir):
    df = pd.read_csv(data_dir / "accounts.csv")
    df["created_at"] = to_utc(df["created_at"])
    return df


@pytest.fixture(scope="session")
def users(data_dir):
    df = pd.read_csv(data_dir / "users.csv")
    for col in ("created_at", "deleted_at"):
        df[col] = to_utc(df[col])
    return df


@pytest.fixture(scope="session")
def plans(data_dir):
    return pd.read_csv(data_dir / "plans.csv")


@pytest.fixture(scope="session")
def subscriptions(data_dir):
    df = pd.read_csv(data_dir / "subscriptions.csv")
    for col in ("started_at", "ended_at"):
        df[col] = to_utc(df[col])
    return df


@pytest.fixture(scope="session")
def invoices(data_dir):
    df = pd.read_csv(data_dir / "invoices.csv")
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["paid_at"] = to_utc(df["paid_at"])
    return df


@pytest.fixture(scope="session")
def event_files(data_dir):
    return sorted((data_dir / "events").glob("????-??.csv.gz"))

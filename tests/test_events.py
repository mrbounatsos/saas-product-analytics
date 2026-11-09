"""Four-million-event audit. Processes gzip partitions in chunks."""
import json

import numpy as np
import pandas as pd
from conftest import START, CUTOFF, CHUNK_SIZE, EVENT_NAMES, to_utc


def event_chunks(event_files):
    for path in event_files:
        for chunk in pd.read_csv(path, compression="gzip", chunksize=CHUNK_SIZE):
            chunk["event_time"] = to_utc(chunk.event_time)
            chunk["ingested_at"] = to_utc(chunk.ingested_at)
            yield path, chunk


def test_monthly_partition_set(event_files):
    expected = {f"{p}.csv.gz" for p in pd.period_range("2024-11", "2026-10", freq="M")}
    assert {p.name for p in event_files} == expected


def test_event_ids_and_total(event_files):
    total = 0
    last_id = 0
    for path, chunk in event_chunks(event_files):
        ids = chunk.event_id.to_numpy(dtype=np.int64)
        assert len(ids) > 0, f"Empty event chunk: {path.name}"
        assert ids[0] == last_id + 1, f"Event ID discontinuity at {path.name}"
        assert np.all(np.diff(ids) == 1), f"Nonconsecutive event IDs in {path.name}"
        last_id = int(ids[-1])
        total += len(chunk)
    assert total == 4_000_000


def test_event_relationships_and_timing(event_files, accounts, users):
    account_created = accounts.set_index("account_id").created_at
    user_lookup = users.set_index("user_id")[["account_id", "created_at", "deleted_at"]]
    for path, chunk in event_chunks(event_files):
        label = path.name
        assert chunk.account_id.isin(account_created.index).all(), label
        assert chunk.user_id.isin(user_lookup.index).all(), label
        expected_signup = chunk.account_id.map(account_created)
        matched_users = user_lookup.reindex(chunk.user_id.to_numpy()).reset_index(drop=True)
        assert matched_users.account_id.eq(chunk.account_id.reset_index(drop=True)).all(), f"user-account mismatch in {label}"
        assert chunk.event_time.notna().all(), label
        assert chunk.event_time.ge(START).all() and chunk.event_time.lt(CUTOFF).all(), label
        assert chunk.event_time.ge(expected_signup).all(), f"event before account signup: {label}"
        assert chunk.event_time.reset_index(drop=True).ge(matched_users.created_at).all(), f"event before user creation: {label}"
        assert (matched_users.deleted_at.isna() | chunk.event_time.reset_index(drop=True).lt(matched_users.deleted_at)).all(), f"event after user deletion: {label}"
        assert chunk.ingested_at.notna().all() and chunk.ingested_at.ge(chunk.event_time).all(), label
        assert chunk.event_time.dt.strftime("%Y-%m").eq(path.name[:7]).all(), f"wrong event partition: {label}"


def test_event_names_and_json_properties(event_files):
    for path, chunk in event_chunks(event_files):
        assert chunk.event_name.isin(EVENT_NAMES).all(), path.name
        try:
            valid = all(isinstance(json.loads(value), dict) for value in chunk.properties)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise AssertionError(f"Invalid JSON in {path.name}") from error
        assert valid, f"Expected JSON objects in {path.name}"

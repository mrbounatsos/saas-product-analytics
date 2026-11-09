"""User-account foreign keys, lifecycle timing, and ownership."""
from conftest import CUTOFF


def test_primary_and_foreign_keys(users, accounts):
    assert users.user_id.notna().all() and users.user_id.is_unique
    assert len(users) == 55_000
    assert users.account_id.isin(accounts.account_id).all()


def test_user_timestamps(users, accounts):
    joined = users.merge(accounts[["account_id", "created_at"]], on="account_id", suffixes=("_user", "_account"), validate="many_to_one")
    assert joined.created_at_user.notna().all()
    assert joined.created_at_user.ge(joined.created_at_account).all()
    assert joined.created_at_user.lt(CUTOFF).all()
    assert (users.deleted_at.isna() | users.deleted_at.gt(users.created_at)).all()
    assert users.deleted_at.dropna().lt(CUTOFF).all()


def test_membership_and_owners(users, accounts):
    counts = users.groupby("account_id").size()
    assert counts.index.isin(accounts.account_id).all()
    assert len(counts) == len(accounts)
    assert counts.ge(1).all()
    assert users.role.isin({"owner", "admin", "member"}).all()
    owners = users[users.role.eq("owner")]
    assert len(owners) == len(accounts)
    assert owners.groupby("account_id").size().eq(1).all()
    assert owners.is_admin.eq(True).all()
    assert users.loc[users.role.eq("admin"), "is_admin"].eq(True).all()
    employee_limit = accounts.set_index("account_id").employee_band
    assert counts.le(employee_limit.reindex(counts.index)).all()

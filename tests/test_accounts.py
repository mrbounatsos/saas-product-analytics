"""Account integrity and coverage; distributions are descriptive, not exact."""
from conftest import START, CUTOFF


def test_primary_key(accounts):
    assert accounts.account_id.notna().all()
    assert accounts.account_id.is_unique
    assert len(accounts) == 10_000


def test_required_values(accounts):
    fields = ["created_at", "company_name", "segment", "country", "acquisition_channel", "employee_band"]
    assert accounts[fields].notna().all().all()
    assert accounts.company_name.str.strip().ne("").all()
    assert accounts.country.str.fullmatch(r"[A-Z]{2}").all()
    assert accounts.employee_band.gt(0).all()


def test_domain_values(accounts):
    assert accounts.segment.isin({"smb", "mid_market", "enterprise"}).all()
    assert accounts.acquisition_channel.isin({"organic", "paid_search", "referral", "partner", "outbound"}).all()


def test_signup_window(accounts):
    assert accounts.created_at.ge(START).all()
    assert accounts.created_at.lt(CUTOFF).all()

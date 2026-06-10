from datetime import date

import pytest

from app.budget_engine import (
    generate_bill_dates,
    occurrences_per_year,
    parse_date,
    calculate_bucket_allocations,
)


class DummyBill:
    def __init__(self, frequency, start_date, amount=100, due_day=None, due_month=None, end_date=None, active=True, include_in_set_aside=True):
        self.frequency = frequency
        self.start_date = start_date
        self.amount = amount
        self.due_day = due_day or parse_date(start_date).day
        self.due_month = due_month
        self.end_date = end_date
        self.active = active
        self.include_in_set_aside = include_in_set_aside


class DummyBucket:
    def __init__(self, name, percentage=0, fixed_amount=None, rounding_increment=1, cap_to_remaining=False, bucket_type="Other"):
        self.name = name
        self.percentage = percentage
        self.fixed_amount = fixed_amount
        self.rounding_increment = rounding_increment
        self.cap_to_remaining = cap_to_remaining
        self.bucket_type = bucket_type


def test_parse_date_accepts_australian_short_year():
    assert parse_date("10/06/26") == date(2026, 6, 10)


def test_weekly_bill_generation_fast_forwards_from_old_start_date():
    bill = DummyBill("Weekly", "2020-01-01")
    due_dates = generate_bill_dates(bill, 2026)

    assert due_dates[0].year == 2026
    assert all(item.year == 2026 for item in due_dates)
    assert len(due_dates) in (52, 53)


def test_monthly_bill_clamps_31st_for_short_months():
    bill = DummyBill("Monthly", "2026-01-31", due_day=31)
    due_dates = generate_bill_dates(bill, 2026)

    assert date(2026, 2, 28) in due_dates
    assert date(2026, 4, 30) in due_dates


def test_occurrences_per_year_rejects_unknown_frequency():
    with pytest.raises(ValueError):
        occurrences_per_year("Every so often")


def test_bucket_remainder_cap_only_applies_to_first_enabled_bucket():
    buckets = [
        DummyBucket("Bills", percentage=80, rounding_increment=1),
        DummyBucket("Remainder A", percentage=50, rounding_increment=1, cap_to_remaining=True),
        DummyBucket("Remainder B", percentage=50, rounding_increment=1, cap_to_remaining=True),
    ]

    rows = calculate_bucket_allocations(buckets, 100)

    assert rows[1]["rounded_amount"] == 20
    assert rows[1]["capped"] is True
    assert rows[2]["rounded_amount"] == 50
    assert rows[2]["capped"] is False

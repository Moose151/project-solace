from datetime import date

from app.forecast import (
    balance_on,
    bill_pays_from_account,
    build_forecast,
    forecast_bill_events,
    forecast_inflow_events,
    safe_to_withdraw,
)


class DummyBill:
    _next_id = 1

    def __init__(self, name, frequency, start_date, amount=100, due_day=None, due_month=None, account_name=None, active=True):
        self.id = DummyBill._next_id
        DummyBill._next_id += 1
        self.name = name
        self.frequency = frequency
        self.start_date = start_date
        self.amount = amount
        self.due_day = due_day or int(start_date[8:10])
        self.due_month = due_month
        self.end_date = None
        self.account_name = account_name
        self.active = active


class DummyOccurrence:
    def __init__(self, bill, due_date, amount=None, status="Upcoming", paid_date=None):
        self.recurring_bill_id = bill.id
        self.bill = bill
        self.due_date = due_date
        self.amount = amount if amount is not None else bill.amount
        self.status = status
        self.paid_date = paid_date


class DummyBucket:
    _next_id = 1

    def __init__(self, name, percentage=0, fixed_amount=None, rounding_increment=1, cap_to_remaining=False, bucket_type="Other", active=True):
        self.id = DummyBucket._next_id
        DummyBucket._next_id += 1
        self.name = name
        self.percentage = percentage
        self.fixed_amount = fixed_amount
        self.rounding_increment = rounding_increment
        self.cap_to_remaining = cap_to_remaining
        self.bucket_type = bucket_type
        self.active = active


class DummyIncome:
    def __init__(self, owner_name, amount, next_pay_date, frequency="Fortnightly", income_scope="Individual", active=True):
        self.owner_name = owner_name
        self.name = f"{owner_name} pay"
        self.amount = amount
        self.frequency = frequency
        self.next_pay_date = next_pay_date
        self.income_scope = income_scope
        self.allocation_mode = "standard"
        self.shared_allocations = []
        self.lump_bucket_id = None
        self.active = active


def test_bill_account_matching():
    everyday = DummyBill("Power", "Monthly", "2026-01-15", account_name="Everyday")
    bills_acct = DummyBill("Water", "Monthly", "2026-01-15", account_name="  BILLS ")
    blank = DummyBill("Rates", "Monthly", "2026-01-15", account_name=None)

    # No configured account name counts every bill.
    assert bill_pays_from_account(everyday, "")
    # Configured name matches case-insensitively with whitespace trimmed.
    assert bill_pays_from_account(bills_acct, "bills")
    assert not bill_pays_from_account(everyday, "bills")
    # Blank bill accounts follow the include_blank setting.
    assert bill_pays_from_account(blank, "bills", include_blank=True)
    assert not bill_pays_from_account(blank, "bills", include_blank=False)


def test_bill_events_project_beyond_stored_occurrences():
    bill = DummyBill("Insurance", "Yearly", "2026-03-10", amount=900, due_month=3)
    occurrences = [DummyOccurrence(bill, "2026-03-10", status="Paid", paid_date="2026-03-10")]

    events = forecast_bill_events([bill], occurrences, date(2026, 7, 1), date(2027, 6, 30))

    # The 2027 occurrence isn't stored (only the budget year is generated),
    # so it must be projected from the recurring rule.
    assert [e["date"] for e in events] == [date(2027, 3, 10)]
    assert events[0]["amount"] == 900


def test_bill_events_status_rules():
    bill = DummyBill("Internet", "Monthly", "2026-01-05", amount=80)
    occurrences = [
        DummyOccurrence(bill, "2026-06-05", status="Upcoming"),           # overdue, still owed
        DummyOccurrence(bill, "2026-07-05", status="Skipped"),            # never counts
        DummyOccurrence(bill, "2026-08-05", status="Paid", paid_date="2026-08-04"),  # paid after snapshot
        DummyOccurrence(bill, "2026-09-05", status="Upcoming", amount=95),
    ]

    events = forecast_bill_events([bill], occurrences, date(2026, 7, 1), date(2026, 9, 30))
    by_date = {e["date"]: e for e in events}

    # Overdue unpaid bill is pulled forward to the forecast start.
    assert by_date[date(2026, 7, 1)]["overdue"] is True
    # Skipped never appears; October is projected but out of window.
    assert date(2026, 7, 5) not in by_date
    # Paid after the snapshot date counts as money leaving the account.
    assert by_date[date(2026, 8, 4)]["label"] == "Internet (paid)"
    # Occurrence amount overrides the recurring amount.
    assert by_date[date(2026, 9, 5)]["amount"] == 95


def test_bill_events_respect_account_filter():
    counted = DummyBill("Power", "Monthly", "2026-01-10", amount=120, account_name="Bills")
    excluded = DummyBill("Gym", "Monthly", "2026-01-10", amount=50, account_name="Everyday")

    events = forecast_bill_events(
        [counted, excluded], [], date(2026, 7, 1), date(2026, 8, 31),
        account_name="Bills", include_blank=True,
    )

    assert {e["label"] for e in events} == {"Power"}


def test_inflow_events_credit_bills_bucket_on_paydays():
    buckets = [
        DummyBucket("Bills", percentage=50, bucket_type="Bills"),
        DummyBucket("Savings", percentage=50, bucket_type="Savings"),
    ]
    income = [DummyIncome("Nick", 1000, "2026-07-02")]

    events = forecast_inflow_events(income, buckets, date(2026, 7, 2), 14, date(2026, 7, 1), date(2026, 7, 31))

    assert [(e["date"], e["amount"]) for e in events] == [
        (date(2026, 7, 2), 500.0),
        (date(2026, 7, 16), 500.0),
        (date(2026, 7, 30), 500.0),
    ]
    assert all(e["label"] == "Nick → Bills" for e in events)


def test_inflow_on_snapshot_date_is_skipped():
    buckets = [DummyBucket("Bills", percentage=50, bucket_type="Bills")]
    income = [DummyIncome("Nick", 1000, "2026-07-02")]

    # Balance recorded on payday already includes that day's transfer.
    events = forecast_inflow_events(income, buckets, date(2026, 7, 2), 14, date(2026, 7, 2), date(2026, 7, 31))

    assert [e["date"] for e in events] == [date(2026, 7, 16), date(2026, 7, 30)]


def test_weekly_income_splits_transfer_across_pay_dates():
    buckets = [DummyBucket("Bills", percentage=50, bucket_type="Bills")]
    income = [DummyIncome("Nick", 500, "2026-07-02", frequency="Weekly")]

    events = forecast_inflow_events(income, buckets, date(2026, 7, 2), 14, date(2026, 7, 1), date(2026, 7, 15))

    # One fortnightly cycle, two weekly pays: the cycle's Bills transfer is
    # split across both pay dates instead of landing all at once.
    assert [(e["date"], e["amount"]) for e in events] == [
        (date(2026, 7, 2), 250.0),
        (date(2026, 7, 9), 250.0),
    ]


def test_build_forecast_flags_shortfalls_and_orders_inflows_first():
    events = [
        {"date": date(2026, 7, 10), "type": "bill", "label": "Insurance", "amount": 700, "overdue": False},
        {"date": date(2026, 7, 10), "type": "inflow", "label": "Nick → Bills", "amount": 400, "overdue": False},
        {"date": date(2026, 7, 20), "type": "bill", "label": "Power", "amount": 100, "overdue": False},
    ]

    result = build_forecast(200, events)

    # Payday transfer lands before the same-day bill: 200 + 400 - 700 = -100.
    assert result["events"][0]["type"] == "inflow"
    assert result["events"][1]["balance_after"] == -100
    assert [e["label"] for e in result["shortfalls"]] == ["Insurance", "Power"]
    assert result["first_negative_date"] == date(2026, 7, 10)
    assert result["min_balance"] == -200
    assert result["min_date"] == date(2026, 7, 20)
    assert result["end_balance"] == -200


def test_safe_to_withdraw_is_limited_by_the_lowest_future_point():
    # Balance today 500; a 400 bill lands before the next 300 payday, so the
    # forecast dips to 100 — that dip is the most that can come out today.
    events = [
        {"date": date(2026, 7, 10), "type": "bill", "label": "Insurance", "amount": 400, "overdue": False},
        {"date": date(2026, 7, 16), "type": "inflow", "label": "Pay", "amount": 300, "overdue": False},
    ]
    result = build_forecast(500, events)

    assert safe_to_withdraw(result, 500, date(2026, 7, 3)) == 100


def test_safe_to_withdraw_is_zero_when_a_shortfall_already_exists():
    events = [
        {"date": date(2026, 7, 10), "type": "bill", "label": "Insurance", "amount": 700, "overdue": False},
    ]
    result = build_forecast(200, events)

    assert safe_to_withdraw(result, 200, date(2026, 7, 3)) == 0


def test_safe_to_withdraw_ignores_events_before_today():
    # The dip on 1 Jul already happened; only future points constrain today.
    events = [
        {"date": date(2026, 7, 1), "type": "bill", "label": "Rent", "amount": 900, "overdue": False},
        {"date": date(2026, 7, 2), "type": "inflow", "label": "Pay", "amount": 1000, "overdue": False},
    ]
    result = build_forecast(1000, events)
    balance_today = balance_on(result, 1000, date(2026, 7, 3))

    assert balance_today == 1100
    assert safe_to_withdraw(result, balance_today, date(2026, 7, 3)) == 1100


def test_balance_on_returns_running_balance_for_any_date():
    events = [
        {"date": date(2026, 7, 10), "type": "inflow", "label": "Pay", "amount": 300, "overdue": False},
        {"date": date(2026, 7, 15), "type": "bill", "label": "Power", "amount": 100, "overdue": False},
    ]
    result = build_forecast(50, events)

    assert balance_on(result, 50, date(2026, 7, 9)) == 50
    assert balance_on(result, 50, date(2026, 7, 10)) == 350
    assert balance_on(result, 50, date(2026, 7, 31)) == 250

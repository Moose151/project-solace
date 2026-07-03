"""Bills-account balance forecasting.

Projects the bills account forward from the latest recorded balance snapshot:
Bills-bucket transfers land on paydays, bill occurrences come out on their due
dates, and any bill that would overdraw the account is flagged as a shortfall.

The snapshot balance is the source of truth for "money in the account now".
Transfers dated on or before the snapshot date are assumed to already be
included in the recorded balance (the payday checklist prompts for a balance
snapshot after transfers are done), while unpaid bills are always still to
come out.
"""

from datetime import timedelta

from .budget_engine import (
    money,
    parse_date,
    generate_bill_dates,
    income_for_cycle,
    calculate_bucket_allocations,
    calculate_person_bucket_allocations,
    calculate_shared_income_bucket_additions,
)


def bill_pays_from_account(bill, account_name, include_blank=True):
    """Return True when a bill is paid from the configured bills account.

    Matching is case-insensitive on the bill's free-text account field. When
    no account name is configured, every bill counts. Bills with a blank
    account are included unless the household opts into strict matching.
    """
    configured = (account_name or "").strip().lower()
    if not configured:
        return True
    bill_account = (getattr(bill, "account_name", None) or "").strip().lower()
    if not bill_account:
        return include_blank
    return bill_account == configured


def forecast_bill_events(bills, occurrences, start_date, end_date, account_name="", include_blank=True):
    """Return outflow events for bills paid from the bills account.

    occurrences should contain every stored occurrence (any status) for the
    window. Rules:
    - Upcoming occurrences come out on their due date. Overdue ones are moved
      to the forecast start because they still have to be paid.
    - Paid occurrences only count when they were paid after the forecast
      start (the money left the account after the balance was recorded).
    - Skipped occurrences never count.
    Due dates with no stored occurrence — typically beyond the generated
    budget year — are projected from each recurring bill's schedule so
    quarterly/annual bills far out still appear.
    """
    start_date = parse_date(start_date)
    end_date = parse_date(end_date)
    covered_bills = [
        bill for bill in bills
        if getattr(bill, "active", True) and bill_pays_from_account(bill, account_name, include_blank)
    ]
    covered_ids = {bill.id for bill in covered_bills}
    stored = set()
    events = []

    for occurrence in occurrences:
        if occurrence.recurring_bill_id not in covered_ids:
            continue
        due = parse_date(occurrence.due_date)
        stored.add((occurrence.recurring_bill_id, due))
        name = occurrence.bill.name if occurrence.bill else "Bill"
        if occurrence.status == "Upcoming":
            event_date = max(due, start_date)
            if event_date > end_date:
                continue
            events.append({
                "date": event_date,
                "type": "bill",
                "label": name,
                "amount": money(occurrence.amount),
                "overdue": due < event_date,
                "due_date": due,
            })
        elif occurrence.status == "Paid":
            paid = parse_date(occurrence.paid_date) if occurrence.paid_date else None
            if paid and start_date < paid <= end_date:
                events.append({
                    "date": paid,
                    "type": "bill",
                    "label": f"{name} (paid)",
                    "amount": money(occurrence.amount),
                    "overdue": False,
                    "due_date": due,
                })

    for bill in covered_bills:
        for year in range(start_date.year, end_date.year + 1):
            for due in generate_bill_dates(bill, year):
                if due <= start_date or due > end_date:
                    continue
                if (bill.id, due) in stored:
                    continue
                events.append({
                    "date": due,
                    "type": "bill",
                    "label": bill.name,
                    "amount": money(bill.amount),
                    "overdue": False,
                    "due_date": due,
                })

    return events


def _distribute_over_pay_dates(events, items, income_total, bills_total, label, start_date, end_date):
    """Split one cycle's Bills transfer across pay dates, proportional to pay.

    Someone paid weekly inside a fortnightly cycle transfers part of their
    Bills amount on each payday rather than all of it on the first one. The
    final pay date absorbs any rounding remainder.
    """
    if bills_total <= 0 or not items:
        return
    remaining = bills_total
    for index, item in enumerate(items):
        if index == len(items) - 1:
            amount = money(remaining)
        else:
            share = (item["amount"] / income_total) if income_total else 1 / len(items)
            amount = money(bills_total * share)
            remaining = money(remaining - amount)
        if amount <= 0:
            continue
        if item["date"] <= start_date or item["date"] > end_date:
            continue
        events.append({
            "date": item["date"],
            "type": "inflow",
            "label": label,
            "amount": amount,
            "overdue": False,
        })


def forecast_inflow_events(income_sources, buckets, cycle_start, interval_days, start_date, end_date):
    """Return payday inflow events for Bills-type bucket transfers.

    cycle_start anchors the pay-cycle grid and interval_days is the household
    cycle length. For every cycle overlapping the window, each person's
    Bills-bucket transfer is credited on their pay date(s), and shared income
    contributions to Bills buckets are credited on the shared income dates.
    Inflows on or before start_date are skipped: the balance snapshot is
    assumed to already include that day's transfers.
    """
    start_date = parse_date(start_date)
    end_date = parse_date(end_date)
    cycle_start = parse_date(cycle_start)
    active_sources = [source for source in income_sources if getattr(source, "active", True)]
    active_buckets = [bucket for bucket in buckets if getattr(bucket, "active", True)]
    bills_bucket_ids = {bucket.id for bucket in active_buckets if bucket.bucket_type == "Bills"}
    if not active_sources or not bills_bucket_ids:
        return []

    events = []
    current = cycle_start
    while current <= end_date:
        cycle_end = current + timedelta(days=interval_days - 1)
        income_items, _ = income_for_cycle(active_sources, current, cycle_end)
        if income_items:
            individual_total = money(sum(
                item["amount"] for item in income_items
                if getattr(item["source"], "income_scope", "Individual") != "Shared"
            ))
            people = calculate_person_bucket_allocations(income_items, active_buckets, individual_total)
            for person in people:
                person_bills_total = money(sum(
                    row["rounded_amount"] for row in person["bucket_allocations"]
                    if row["bucket"].id in bills_bucket_ids
                ))
                _distribute_over_pay_dates(
                    events, person["items"], person["income_total"], person_bills_total,
                    f"{person['person']} → Bills", start_date, end_date,
                )

            shared_items = [
                item for item in income_items
                if getattr(item["source"], "income_scope", "Individual") == "Shared"
            ]
            if shared_items:
                additions, standard_pool = calculate_shared_income_bucket_additions(income_items, active_buckets)
                shared_bills_total = money(sum(
                    amount for bucket_id, amount in additions.items() if bucket_id in bills_bucket_ids
                ))
                if standard_pool:
                    pool_rows = calculate_bucket_allocations(active_buckets, standard_pool)
                    shared_bills_total = money(shared_bills_total + sum(
                        row["rounded_amount"] for row in pool_rows
                        if row["bucket"].id in bills_bucket_ids
                    ))
                shared_income_total = money(sum(item["amount"] for item in shared_items))
                _distribute_over_pay_dates(
                    events, shared_items, shared_income_total, shared_bills_total,
                    "Shared income → Bills", start_date, end_date,
                )
        current += timedelta(days=interval_days)

    return events


def build_forecast(starting_balance, events):
    """Sort events and compute the running balance and shortfalls.

    Inflows are applied before bills that fall on the same day (payday
    transfers happen before payments go out). A shortfall is a bill that
    leaves the account below zero — there is not enough in the account to pay
    it when it is due, after all earlier bills and transfers are accounted for.
    """
    ordered = sorted(events, key=lambda e: (e["date"], 0 if e["type"] == "inflow" else 1, e["label"].lower()))
    balance = money(starting_balance)
    shortfalls = []
    min_balance = balance
    min_date = None
    first_negative_date = None

    for event in ordered:
        if event["type"] == "inflow":
            balance = money(balance + event["amount"])
        else:
            balance = money(balance - event["amount"])
        event["balance_after"] = balance
        event["shortfall"] = event["type"] == "bill" and balance < 0
        if event["shortfall"]:
            shortfalls.append(event)
        if first_negative_date is None and balance < 0:
            first_negative_date = event["date"]
        if balance < min_balance:
            min_balance = balance
            min_date = event["date"]

    return {
        "events": ordered,
        "shortfalls": shortfalls,
        "min_balance": money(min_balance),
        "min_date": min_date,
        "first_negative_date": first_negative_date,
        "end_balance": balance,
    }


def balance_on(forecast, starting_balance, target_date):
    """Return the projected balance at the end of target_date."""
    target_date = parse_date(target_date)
    balance = money(starting_balance)
    for event in forecast["events"]:
        if event["date"] > target_date:
            break
        balance = event["balance_after"]
    return balance

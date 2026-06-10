from datetime import date, datetime, timedelta
from calendar import monthrange
from dateutil.relativedelta import relativedelta


def parse_date(value):
    """Convert common date inputs into a date object.

    HTML date inputs usually submit YYYY-MM-DD. Australian users may also
    manually type Australian-style dates, including DD/MM/YYYY, DD-MM-YYYY,
    DD/MM/YY, and DD-MM-YY. Supporting these formats prevents a bad date
    entry from crashing the app.
    """
    if not value:
        return None

    if isinstance(value, date):
        return value

    value = str(value).strip()

    supported_formats = (
        "%Y-%m-%d",  # 2026-06-08, from HTML date inputs
        "%d/%m/%Y",  # 08/06/2026
        "%d-%m-%Y",  # 08-06-2026
        "%d/%m/%y",  # 08/06/26
        "%d-%m-%y",  # 08-06-26
    )

    for date_format in supported_formats:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    raise ValueError(
        f"Invalid date format: {value}. Use YYYY-MM-DD, DD/MM/YYYY, or DD/MM/YY."
    )


def money(value):
    """Round money values to two decimal places for display/calculation consistency."""
    return round(float(value or 0), 2)


def occurrences_per_year(frequency):
    """Return the annual multiplier used for average set-aside calculations.

    Unknown frequencies are treated as programming/data errors. Returning zero
    would silently understate the household set-aside requirement.
    """
    mapping = {
        "Weekly": 52,
        "Fortnightly": 26,
        "Monthly": 12,
        "Quarterly": 4,
        "Six-monthly": 2,
        "Yearly": 1,
    }
    if frequency not in mapping:
        raise ValueError(f"Unknown bill frequency: {frequency}")
    return mapping[frequency]


def annual_cost(bill):
    return money(bill.amount * occurrences_per_year(bill.frequency))


def fortnightly_bill_amount(bill):
    if not bill.include_in_set_aside or not bill.active:
        return 0
    return money(annual_cost(bill) / 26)


def clamp_due_day(year, month, due_day):
    """Handle due days such as 31 in months that only have 30 or fewer days."""
    final_day = monthrange(year, month)[1]
    return min(int(due_day), final_day)


def generate_bill_dates(bill, year):
    """Generate due dates for a recurring bill within a budget year.

    The recurring bill stores the rule. Generated bill occurrences are the dated
    records that appear in the calendar and can be marked as paid.
    """
    start = parse_date(bill.start_date)
    end = parse_date(bill.end_date) if bill.end_date else date(year, 12, 31)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    # Restrict generation to the selected budget year.
    window_start = max(start, year_start)
    window_end = min(end, year_end)
    if window_start > window_end:
        return []

    due_dates = []

    if bill.frequency in ["Monthly", "Quarterly", "Six-monthly", "Yearly"]:
        interval_months = {
            "Monthly": 1,
            "Quarterly": 3,
            "Six-monthly": 6,
            "Yearly": 12,
        }[bill.frequency]

        # Use due_month when relevant; otherwise start in January.
        current_month = bill.due_month or 1
        current = date(year, current_month, clamp_due_day(year, current_month, bill.due_day))

        # Move forward until we reach the generation window.
        while current < window_start:
            next_month = current + relativedelta(months=interval_months)
            current = date(next_month.year, next_month.month, clamp_due_day(next_month.year, next_month.month, bill.due_day))

        while current <= window_end:
            if current.year == year:
                due_dates.append(current)
            next_month = current + relativedelta(months=interval_months)
            current = date(next_month.year, next_month.month, clamp_due_day(next_month.year, next_month.month, bill.due_day))

    elif bill.frequency in ["Weekly", "Fortnightly"]:
        interval_days = 7 if bill.frequency == "Weekly" else 14

        # Fast-forward directly to the first occurrence in the generation
        # window. This avoids stepping one interval at a time for bills that
        # started years ago.
        days_since_start = (window_start - start).days
        steps = max(0, days_since_start // interval_days)
        current = start + timedelta(days=steps * interval_days)
        if current < window_start:
            current += timedelta(days=interval_days)

        while current <= window_end:
            due_dates.append(current)
            current += timedelta(days=interval_days)

    return due_dates


def get_paydays(first_payday, year, frequency="fortnightly"):
    """Generate payday dates for a selected year.

    Supports weekly and fortnightly household pay cycles.
    """
    current = parse_date(first_payday)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    interval = 7 if frequency == "weekly" else 14

    while current < year_start:
        current += timedelta(days=interval)

    paydays = []
    while current <= year_end:
        paydays.append(current)
        current += timedelta(days=interval)
    return paydays


def current_pay_cycle(first_payday, today=None, frequency="fortnightly"):
    """Return the current pay-cycle start, end, and next payday."""
    today = today or date.today()
    payday = parse_date(first_payday)
    interval = 7 if frequency == "weekly" else 14

    while payday <= today:
        payday += timedelta(days=interval)

    cycle_start = payday - timedelta(days=interval)
    cycle_end = payday - timedelta(days=1)
    return cycle_start, cycle_end, payday


def income_interval_days(income_source):
    """Return the payment interval in days for an income source.

    Weekly and Fortnightly are the only supported income frequencies.
    Any unrecognised value falls back to fortnightly so old data never breaks.
    """
    freq = getattr(income_source, "frequency", "Fortnightly") or "Fortnightly"
    return 7 if freq.lower() == "weekly" else 14


def next_income_pay_date(income_source, today=None):
    """Return the next expected pay date for an income source.

    The stored income date is treated as a known/anchor payday, not a value that
    must be manually updated each cycle. This keeps old anchor dates useful
    while still showing the actual upcoming payday.
    """
    today = today or date.today()
    if not income_source or not getattr(income_source, "active", True):
        return None
    current = parse_date(getattr(income_source, "next_pay_date", None))
    if not current:
        return None
    interval = income_interval_days(income_source)
    while current < today:
        current += timedelta(days=interval)
    return current


def latest_income_pay_date(income_source, today=None):
    """Return the most recent pay date on or before today for an income source."""
    today = today or date.today()
    current = parse_date(getattr(income_source, "next_pay_date", None))
    if not current:
        return None
    interval = income_interval_days(income_source)
    while current + timedelta(days=interval) <= today:
        current += timedelta(days=interval)
    return current


def household_pay_cycle(first_payday, income_sources=None, today=None, frequency="fortnightly"):
    """Return the household pay-cycle using income sources as the source of truth.

    If active income sources exist, the earliest income-source anchor date is used
    as the household cycle anchor. This supports households where two people are
    paid on different days in the same cycle while avoiding the confusing global
    Settings.first_payday value becoming stale or incorrect. If no active income
    sources exist, the legacy first_payday setting is used as a fallback.
    """
    today = today or date.today()
    interval = 7 if frequency == "weekly" else 14
    active_sources = [source for source in (income_sources or []) if getattr(source, "active", False)]

    anchors = []
    for source in active_sources:
        anchor = parse_date(getattr(source, "next_pay_date", None))
        if anchor:
            anchors.append(anchor)

    if anchors:
        anchor = min(anchors)
        cycle_start = anchor
        while cycle_start + timedelta(days=interval) <= today:
            cycle_start += timedelta(days=interval)
        cycle_end = cycle_start + timedelta(days=interval - 1)
        next_payday = cycle_start if today <= cycle_start else cycle_start + timedelta(days=interval)
        return cycle_start, cycle_end, next_payday

    return current_pay_cycle(first_payday, today=today, frequency=frequency)


def fortnights_until(target_date, first_payday, today=None):
    """Count pay periods from now until the target date, minimum of one.

    Named 'fortnights_until' for historical reasons but uses the household
    cycle interval (weekly or fortnightly) when a frequency is derivable.
    Always counts fortnightly periods for purchase planning purposes since
    that is how the set-aside calculation is expressed.
    """
    today = today or date.today()
    target = parse_date(target_date)
    payday = parse_date(first_payday)

    while payday < today:
        payday += timedelta(days=14)

    count = 0
    while payday <= target:
        count += 1
        payday += timedelta(days=14)

    return max(count, 1)


def planned_purchase_fortnightly_amount(purchase, first_payday):
    if purchase.status != "Active":
        return 0
    remaining = max(purchase.target_amount - purchase.amount_saved, 0)
    periods = fortnights_until(purchase.target_date, first_payday)
    return money(remaining / periods)


def is_shared_purchase(purchase):
    """Return True when a planned purchase should be part of household set-aside."""
    return getattr(purchase, "purchase_scope", "Shared") != "Individual"


def planned_purchase_scope_label(purchase):
    if getattr(purchase, "purchase_scope", "Shared") == "Individual":
        owner = getattr(purchase, "owner_name", None) or "Unassigned"
        return f"Individual — {owner}"
    return "Shared"


def round_to_increment(value, increment):
    """Round a transfer amount to the nearest configured dollar increment."""
    increment = int(increment or 1)
    if increment <= 1:
        return money(value)
    return money(round(float(value or 0) / increment) * increment)


def generate_income_dates(income_source, cycle_start, cycle_end):
    """Generate expected income dates that fall inside a pay cycle.

    Supports weekly and fortnightly income sources.
    """
    if not income_source.active:
        return []
    current = parse_date(income_source.next_pay_date)
    if not current:
        return []
    cycle_start = parse_date(cycle_start)
    cycle_end = parse_date(cycle_end)
    interval = income_interval_days(income_source)
    while current < cycle_start:
        current += timedelta(days=interval)
    dates = []
    while current <= cycle_end:
        dates.append(current)
        current += timedelta(days=interval)
    return dates


def income_for_cycle(income_sources, cycle_start, cycle_end):
    """Return expected income items and total for a pay cycle.

    Individual and shared income sources are both included here so callers
    have the full picture. Callers that need to separate them should filter
    on item["source"].income_scope.
    """
    items = []
    for source in income_sources:
        for pay_date in generate_income_dates(source, cycle_start, cycle_end):
            items.append({"source": source, "date": pay_date, "amount": money(source.amount)})
    items.sort(key=lambda item: item["date"])
    return items, money(sum(item["amount"] for item in items))


def calculate_bucket_allocations(buckets, income_total, household_income_total=None):
    """Calculate raw and rounded bucket amounts for a pay cycle.

    For the household view, income_total and household_income_total are the same.
    For an individual person/source view, income_total is that person's pay and
    household_income_total is the combined pay. Percentage buckets are applied to
    the person's own pay. Fixed amount buckets are split proportionally by income
    share so a fixed household transfer is not duplicated for each person.

    This function only handles individual income. Shared income is applied
    separately via apply_shared_income_allocations and added to bucket totals
    after per-person splits are done.
    """
    rows = []
    allocated_total = money(0)
    household_income_total = money(household_income_total if household_income_total is not None else income_total)
    remainder_cap_seen = False

    for bucket in buckets:
        if bucket.fixed_amount not in [None, ""]:
            income_share = (income_total / household_income_total) if household_income_total else 0
            raw_amount = money(bucket.fixed_amount * income_share)
            target_label = f"Fixed ${money(bucket.fixed_amount):.2f} split by income"
        else:
            raw_amount = money(income_total * (bucket.percentage / 100))
            target_label = f"{money(bucket.percentage)}%"

        rounded_amount = round_to_increment(raw_amount, bucket.rounding_increment)
        remaining_before = money(income_total - allocated_total)
        capped = False

        # Only the first enabled remainder bucket is allowed to cap itself to
        # the remaining income. Later remainder flags are ignored defensively;
        # the UI/startup cleanup also tries to enforce a single remainder bucket.
        cap_enabled = bool(getattr(bucket, "cap_to_remaining", False)) and not remainder_cap_seen
        if cap_enabled:
            remainder_cap_seen = True
        if cap_enabled and rounded_amount > remaining_before:
            rounded_amount = money(max(remaining_before, 0))
            capped = True

        allocated_total = money(allocated_total + rounded_amount)

        rows.append({
            "bucket": bucket,
            "raw_amount": money(raw_amount),
            "rounded_amount": rounded_amount,
            "remaining_before": remaining_before,
            "capped": capped,
            "target_label": target_label,
            "percentage_of_income": money((rounded_amount / income_total * 100) if income_total else 0),
        })
    return rows


def apply_shared_income_allocations(income_source, buckets_by_id):
    """Return a list of allocation rows for one shared income source.

    Each row is {"bucket": Bucket, "amount": float, "label": str}.

    allocation_mode == "standard":
        Returns an empty list. The caller should add the income amount to the
        household pool and let the standard bucket math handle it.

    allocation_mode == "lump":
        The full amount goes to the nominated bucket. Returns one row.

    allocation_mode == "custom":
        Iterates SharedIncomeAllocation rows in sort_order. The row flagged
        is_remainder=True receives whatever is left after all others are applied.
        If no remainder row is defined, any unallocated amount is silently dropped
        (the UI should warn the user, but the engine stays safe).
    """
    mode = getattr(income_source, "allocation_mode", "standard") or "standard"
    amount = money(income_source.amount)
    rows = []

    if mode == "standard":
        return []

    if mode == "lump":
        bucket = buckets_by_id.get(income_source.lump_bucket_id)
        if bucket:
            rows.append({"bucket": bucket, "amount": amount, "label": f"Lump → {bucket.name}"})
        return rows

    if mode == "custom":
        allocations = getattr(income_source, "shared_allocations", [])
        remainder_row = None
        allocated = money(0)

        for alloc in sorted(allocations, key=lambda a: a.sort_order):
            bucket = buckets_by_id.get(alloc.bucket_id)
            if not bucket:
                continue
            if alloc.is_remainder:
                remainder_row = (alloc, bucket)
                continue
            alloc_amount = money(amount * (alloc.percentage / 100))
            allocated = money(allocated + alloc_amount)
            rows.append({"bucket": bucket, "amount": alloc_amount, "label": f"{money(alloc.percentage)}% → {bucket.name}"})

        if remainder_row:
            _, bucket = remainder_row
            leftover = money(max(amount - allocated, 0))
            rows.append({"bucket": bucket, "amount": leftover, "label": f"Remainder → {bucket.name}"})

        return rows

    return []


def income_totals_by_person(income_items):
    """Group expected pay-cycle income by person.

    Only individual-scoped income sources are included. Shared income sources
    are excluded here; they are handled separately in calculate_shared_income_bucket_additions.
    """
    people = {}
    for item in income_items:
        source = item["source"]
        if getattr(source, "income_scope", "Individual") == "Shared":
            continue
        person = getattr(source, "owner_name", None) or "Household"
        people.setdefault(person, {"person": person, "income_total": 0, "items": []})
        people[person]["income_total"] = money(people[person]["income_total"] + item["amount"])
        people[person]["items"].append(item)
    return sorted(people.values(), key=lambda row: row["person"].lower())


def calculate_shared_income_bucket_additions(income_items, buckets):
    """Return per-bucket amount additions from shared income sources.

    Returns a dict of {bucket_id: total_amount} for all shared income sources
    that use lump or custom allocation modes, plus the total shared income that
    flows back into the standard bucket pool (standard-mode shared income).

    Callers add the per-bucket amounts on top of the standard bucket allocations
    when building the combined household view, and add standard_pool_amount to
    the household income total before running standard bucket math.
    """
    bucket_additions = {}
    standard_pool_amount = money(0)
    buckets_by_id = {b.id: b for b in buckets}

    for item in income_items:
        source = item["source"]
        if getattr(source, "income_scope", "Individual") != "Shared":
            continue

        mode = getattr(source, "allocation_mode", "standard") or "standard"

        if mode == "standard":
            standard_pool_amount = money(standard_pool_amount + item["amount"])
            continue

        for row in apply_shared_income_allocations(source, buckets_by_id):
            bid = row["bucket"].id
            bucket_additions[bid] = money(bucket_additions.get(bid, 0) + row["amount"])

    return bucket_additions, standard_pool_amount


def calculate_person_bucket_allocations(income_items, buckets, household_income_total):
    """Return bucket transfer rows for each person's individual pay.

    Shared income sources are excluded — they are not attributed to any person.
    household_income_total should already exclude shared income so percentages
    reflect only the individual income pool.
    """
    people = income_totals_by_person(income_items)
    for person in people:
        allocations = calculate_bucket_allocations(
            buckets,
            person["income_total"],
            household_income_total=household_income_total,
        )
        person["bucket_allocations"] = allocations
        person["bucket_total"] = money(sum(row["rounded_amount"] for row in allocations))
        person["remaining"] = money(person["income_total"] - person["bucket_total"])
        person["bills_bucket_total"] = money(sum(
            row["rounded_amount"]
            for row in allocations
            if row["bucket"].bucket_type in ["Bills", "Planned purchases"]
        ))
    return people

from datetime import date, datetime, timedelta
from calendar import monthrange
from dateutil.relativedelta import relativedelta


def parse_date(value):
    """Convert common date inputs into a date object.

    HTML date inputs usually submit YYYY-MM-DD. Australian users may also
    manually type DD/MM/YYYY or DD-MM-YYYY. Supporting all three prevents
    a bad date entry from crashing the app.
    """
    if not value:
        return None

    if isinstance(value, date):
        return value

    value = str(value).strip()

    for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue

    raise ValueError(
        f"Invalid date format: {value}. Use YYYY-MM-DD or DD/MM/YYYY."
    )


def money(value):
    """Round money values to two decimal places for display/calculation consistency."""
    return round(float(value or 0), 2)


def occurrences_per_year(frequency):
    """Return the annual multiplier used for average set-aside calculations."""
    mapping = {
        "Weekly": 52,
        "Fortnightly": 26,
        "Monthly": 12,
        "Quarterly": 4,
        "Six-monthly": 2,
        "Yearly": 1,
    }
    return mapping.get(frequency, 0)


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
        current = start
        while current < window_start:
            current += timedelta(days=interval_days)
        while current <= window_end:
            due_dates.append(current)
            current += timedelta(days=interval_days)

    return due_dates


def get_paydays(first_payday, year):
    """Generate fortnightly payday dates for a selected year."""
    current = parse_date(first_payday)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    while current < year_start:
        current += timedelta(days=14)

    paydays = []
    while current <= year_end:
        paydays.append(current)
        current += timedelta(days=14)
    return paydays


def current_pay_cycle(first_payday, today=None):
    """Return the current pay-cycle start, end, and next payday."""
    today = today or date.today()
    payday = parse_date(first_payday)

    while payday <= today:
        payday += timedelta(days=14)

    cycle_start = payday - timedelta(days=14)
    cycle_end = payday - timedelta(days=1)
    return cycle_start, cycle_end, payday


def fortnights_until(target_date, first_payday, today=None):
    """Count paydays from now until the target date, minimum of one."""
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

import csv
import io
import os
import shutil
import tempfile
from calendar import Calendar, month_name
from datetime import date, datetime, timedelta
from zipfile import ZipFile, ZIP_DEFLATED

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, send_file, current_app, session
from flask_login import login_user, logout_user, login_required
from werkzeug.security import check_password_hash

from .models import db, User, Settings, Category, RecurringBill, BillOccurrence, PlannedPurchase, AccountBalanceSnapshot, IncomeSource, Bucket, DashboardWidget, PaydayChecklistItem, AuditLog, NotificationSetting
from .forms import LoginForm, SettingsForm, CategoryForm, RecurringBillForm, PlannedPurchaseForm, AccountBalanceForm, IncomeSourceForm, BucketForm, NotificationSettingsForm
from .budget_engine import (
    annual_cost, fortnightly_bill_amount, generate_bill_dates,
    planned_purchase_fortnightly_amount, current_pay_cycle, money, parse_date, income_for_cycle,
    generate_income_dates, calculate_bucket_allocations, calculate_person_bucket_allocations
)

main = Blueprint("main", __name__)


def get_settings():
    return Settings.query.first()


def category_choices(kind):
    """Return category choices for bill or purchase forms."""
    rows = Category.query.filter(Category.active.is_(True)).order_by(Category.name).all()
    choices = [(0, "Uncategorised")]
    for category in rows:
        if category.category_type in [kind, "Both"]:
            choices.append((category.id, category.name))
    return choices


def regenerate_bill_occurrences(bill, scope="future_unpaid"):
    """Regenerate unpaid occurrences for a recurring bill.

    Paid occurrences are kept so payment history is not destroyed. By default,
    only future unpaid occurrences are replaced. This makes editing safer after
    the app has been used for a while. The old behaviour can still be requested
    by using scope="all_unpaid".
    """
    settings = get_settings()
    budget_year = settings.budget_year
    today_iso = date.today().isoformat()

    query = BillOccurrence.query.filter(
        BillOccurrence.recurring_bill_id == bill.id,
        BillOccurrence.status != "Paid",
    )
    if scope == "future_unpaid":
        query = query.filter(BillOccurrence.due_date >= today_iso)
    query.delete(synchronize_session=False)

    for due_date in generate_bill_dates(bill, budget_year):
        due_iso = due_date.isoformat()
        if scope == "future_unpaid" and due_iso < today_iso:
            continue
        existing = BillOccurrence.query.filter_by(
            recurring_bill_id=bill.id,
            due_date=due_iso,
        ).first()
        if not existing:
            db.session.add(BillOccurrence(
                recurring_bill_id=bill.id,
                due_date=due_iso,
                amount=bill.amount,
                status="Upcoming",
            ))



def enforce_single_remainder_bucket(preferred_bucket=None):
    """Ensure only one bucket has the remainder-cap option enabled.

    The pay split calculation is ordered, so allowing multiple remainder buckets
    would make the later ones confusing. When a preferred bucket is provided, it
    becomes the only capped bucket; otherwise the first sorted capped bucket is kept.
    """
    capped = Bucket.query.filter(Bucket.cap_to_remaining.is_(True)).order_by(Bucket.sort_order, Bucket.name).all()
    if not capped:
        return
    keep = preferred_bucket if preferred_bucket and preferred_bucket.cap_to_remaining else capped[0]
    for bucket in capped:
        if bucket.id != keep.id:
            bucket.cap_to_remaining = False




def prepare_bucket_form_for_display(form, bucket=None):
    """Set the bucket form's amount type based on saved values.

    Buckets can use either a percentage or a fixed household amount. The form
    keeps this explicit so users do not accidentally enter both.
    """
    if bucket and bucket.fixed_amount is not None:
        form.allocation_method.data = "fixed"
    elif not form.allocation_method.data:
        form.allocation_method.data = "percentage"


def apply_bucket_form(bucket, form):
    """Apply bucket form data while enforcing one amount type only."""
    bucket.name = form.name.data.strip()
    bucket.allocation_method = getattr(form, "allocation_method", None) and form.allocation_method.data

    if form.allocation_method.data == "fixed":
        fixed = form.fixed_amount.data
        if fixed is None or fixed <= 0:
            form.fixed_amount.errors.append("Enter a fixed amount greater than $0.")
            return False
        bucket.fixed_amount = money(fixed)
        bucket.percentage = 0
    else:
        percentage = form.percentage.data
        if percentage is None or percentage < 0:
            form.percentage.errors.append("Enter a percentage of 0 or higher.")
            return False
        bucket.percentage = money(percentage)
        bucket.fixed_amount = None

    bucket.rounding_increment = form.rounding_increment.data
    bucket.cap_to_remaining = bool(form.cap_to_remaining.data)
    bucket.bucket_type = form.bucket_type.data
    bucket.active = bool(form.active.data)
    bucket.sort_order = form.sort_order.data or 0
    bucket.notes = form.notes.data
    return True

def normalise_date_string(value):
    parsed = parse_date(value)
    return parsed.isoformat() if parsed else None


def get_or_create_category(name, category_type="Bill"):
    if not name:
        return None
    name = str(name).strip()
    if not name:
        return None
    category = Category.query.filter(db.func.lower(Category.name) == name.lower()).first()
    if category:
        return category
    category = Category(name=name, category_type=category_type, active=True)
    db.session.add(category)
    db.session.flush()
    return category



def audit(action, entity_type=None, entity_name=None, details=None):
    """Record a lightweight audit event for important user actions."""
    try:
        db.session.add(AuditLog(
            created_at=datetime.now().isoformat(timespec="seconds"),
            action=action,
            entity_type=entity_type,
            entity_name=entity_name,
            details=details,
        ))
    except Exception:
        # Audit logging should never block the main workflow.
        pass


def get_database_path():
    """Return the SQLite database path from the configured SQLAlchemy URI."""
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    return uri.replace("sqlite:///", "") if uri.startswith("sqlite:///") else uri


def parse_bill_import_rows(rows):
    """Convert uploaded rows into a preview with validation before committing."""
    parsed_rows = []
    errors = 0
    allowed_frequencies = {"Weekly", "Fortnightly", "Monthly", "Quarterly", "Six-monthly", "Yearly"}
    for index, row in enumerate(rows, start=2):
        preview = {"source_row": index, "errors": []}
        try:
            name = str(pick(row, "name", "bill", "bill_name")).strip()
            if not name:
                preview["errors"].append("Missing name")
            amount = float(pick(row, "amount", "cost", default=0))
            if amount <= 0:
                preview["errors"].append("Amount must be greater than 0")
            frequency = str(pick(row, "frequency", default="Monthly")).strip().title()
            if frequency == "Six Monthly":
                frequency = "Six-monthly"
            if frequency not in allowed_frequencies:
                preview["errors"].append(f"Unsupported frequency: {frequency}")
            due_day = int(float(pick(row, "due_day", "day", "due", default=1)))
            if due_day < 1 or due_day > 31:
                preview["errors"].append("Due day must be 1-31")
            due_month_raw = pick(row, "due_month", "month", default="")
            due_month = int(float(due_month_raw)) if due_month_raw not in [None, ""] else None
            if due_month is not None and (due_month < 1 or due_month > 12):
                preview["errors"].append("Due month must be 1-12")
            start_date = normalise_date_string(pick(row, "start_date", "start", default=f"{get_settings().budget_year}-01-01"))
            end_value = pick(row, "end_date", "end", default="")
            end_date = normalise_date_string(end_value) if end_value else None
            category_name = str(pick(row, "category", default="")).strip()
            active = str(pick(row, "active", default="yes")).strip().lower() not in ["no", "false", "0"]
            autopay = str(pick(row, "autopay", "auto_pay", default="no")).strip().lower() in ["yes", "true", "1"]
            include = str(pick(row, "include_in_set_aside", "include", default="yes")).strip().lower() not in ["no", "false", "0"]
            preview.update({
                "name": name,
                "amount": amount,
                "frequency": frequency,
                "due_day": due_day,
                "due_month": due_month,
                "start_date": start_date,
                "end_date": end_date,
                "category": category_name,
                "active": active,
                "autopay": autopay,
                "account_name": str(pick(row, "account_name", "account", default="")).strip(),
                "include_in_set_aside": include,
                "notes": str(pick(row, "notes", default="")).strip(),
            })
        except Exception as exc:
            preview["errors"].append(str(exc))
        if preview["errors"]:
            errors += 1
        parsed_rows.append(preview)
    return parsed_rows, errors


def ensure_payday_checklist_items(settings, cycle_start, income_items, person_bucket_allocations, bucket_allocations):
    """Create checklist items for the current pay cycle if they do not already exist."""
    existing = {item.item_key: item for item in PaydayChecklistItem.query.filter_by(cycle_start=cycle_start.isoformat()).all()}
    required = []
    order = 10
    required.append(("confirm_income", "Confirm all expected income has arrived", None, order)); order += 10
    for person in person_bucket_allocations:
        for row in person.get("bucket_allocations", []):
            amount = money(row["rounded_amount"])
            if amount <= 0:
                continue
            key = f"transfer_{person['person']}_{row['bucket'].id}".lower().replace(" ", "_")
            label = f"{person['person']}: transfer {settings.currency_symbol}{amount:.2f} to {row['bucket'].name}"
            required.append((key, label, amount, order)); order += 10
    required.append(("review_due_bills", "Review bills due before next payday", None, order)); order += 10
    required.append(("record_balance", "Optional: record the bills/set-aside account balance", None, order))
    for key, label, amount, sort_order in required:
        if key not in existing:
            db.session.add(PaydayChecklistItem(
                cycle_start=cycle_start.isoformat(),
                item_key=key,
                label=label,
                amount=amount,
                completed=False,
                sort_order=sort_order,
            ))
    db.session.commit()
    return PaydayChecklistItem.query.filter_by(cycle_start=cycle_start.isoformat()).order_by(PaydayChecklistItem.sort_order).all()

def get_dashboard_widgets():
    """Return dashboard widgets in display order and a quick enabled lookup."""
    widgets = DashboardWidget.query.order_by(DashboardWidget.sort_order, DashboardWidget.title).all()
    if not widgets:
        # Existing databases should normally be seeded at startup. This fallback
        # prevents a blank dashboard if the table exists but has no rows.
        defaults = [
            ("set_aside_summary", "Set-aside summary", True, 10, "wide"),
            ("income_summary", "Income summary", True, 20, "medium"),
            ("bucket_summary", "Bucket summary", True, 30, "medium"),
            ("per_person_contributions", "Individual contributions", True, 40, "wide"),
            ("bills_bucket_health", "Bills bucket health", True, 45, "medium"),
            ("payday_checklist", "Payday checklist", True, 48, "medium"),
            ("due_before_next_payday", "Due before next payday", True, 50, "wide"),
        ]
        for key, title, enabled, sort_order, size in defaults:
            db.session.add(DashboardWidget(widget_key=key, title=title, enabled=enabled, sort_order=sort_order, size=size))
        db.session.commit()
        widgets = DashboardWidget.query.order_by(DashboardWidget.sort_order, DashboardWidget.title).all()
    enabled = {widget.widget_key for widget in widgets if widget.enabled}
    return widgets, enabled


@main.context_processor
def inject_globals():
    settings = get_settings()
    theme_mode = settings.theme if settings and settings.theme in ["Light", "Dark", "Auto"] else "Light"
    return {"settings": settings, "money": money, "theme_mode": theme_mode}


@main.route("/health")
def health():
    return {"status": "ok", "app": "Project Solace"}


@main.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            return redirect(url_for("main.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html", form=form)


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


@main.route("/")
@login_required
def dashboard():
    settings = get_settings()
    bills = RecurringBill.query.filter_by(active=True).order_by(RecurringBill.name).all()
    purchases = PlannedPurchase.query.filter_by(status="Active").order_by(PlannedPurchase.target_date).all()

    bill_fortnightly_total = money(sum(fortnightly_bill_amount(b) for b in bills))
    purchase_fortnightly_total = money(sum(planned_purchase_fortnightly_amount(p, settings.first_payday) for p in purchases))
    buffer_amount = money(settings.default_buffer_amount)
    total_set_aside = money(bill_fortnightly_total + purchase_fortnightly_total + buffer_amount)

    today = date.today()
    cycle_start, cycle_end, next_payday = current_pay_cycle(settings.first_payday, today=today)

    income_sources = IncomeSource.query.filter_by(active=True).order_by(IncomeSource.next_pay_date, IncomeSource.name).all()
    income_items, income_total = income_for_cycle(income_sources, cycle_start, cycle_end)
    buckets = Bucket.query.filter_by(active=True).order_by(Bucket.sort_order, Bucket.name).all()
    bucket_allocations = calculate_bucket_allocations(buckets, income_total)
    person_bucket_allocations = calculate_person_bucket_allocations(income_items, buckets, income_total)
    total_bucket_amount = money(sum(row["rounded_amount"] for row in bucket_allocations))
    remaining_after_buckets = money(income_total - total_bucket_amount)
    bills_bucket_total = money(sum(row["rounded_amount"] for row in bucket_allocations if row["bucket"].bucket_type == "Bills"))
    bills_and_purchases_bucket_total = money(sum(row["rounded_amount"] for row in bucket_allocations if row["bucket"].bucket_type in ["Bills", "Planned purchases"]))
    bills_bucket_delta = money(bills_bucket_total - bill_fortnightly_total)
    bills_bucket_status = "covered" if bills_bucket_delta >= 0 else "short"

    checklist_items = ensure_payday_checklist_items(settings, cycle_start, income_items, person_bucket_allocations, bucket_allocations)
    checklist_completed = sum(1 for item in checklist_items if item.completed)
    checklist_total = len(checklist_items)

    notifications = NotificationSetting.query.first()

    due_before_next_payday = BillOccurrence.query.filter(
        BillOccurrence.due_date >= today.isoformat(),
        BillOccurrence.due_date <= next_payday.isoformat(),
        BillOccurrence.status == "Upcoming",
    ).order_by(BillOccurrence.due_date).all()

    due_next_30_days = BillOccurrence.query.filter(
        BillOccurrence.due_date >= today.isoformat(),
        BillOccurrence.due_date <= (today + timedelta(days=30)).isoformat(),
        BillOccurrence.status == "Upcoming",
    ).order_by(BillOccurrence.due_date).all()

    overdue = BillOccurrence.query.filter(
        BillOccurrence.due_date < today.isoformat(),
        BillOccurrence.status == "Upcoming",
    ).order_by(BillOccurrence.due_date).all()

    monthly_total = money(sum(annual_cost(b) for b in bills) / 12)
    annual_total = money(sum(annual_cost(b) for b in bills))

    latest_balance = AccountBalanceSnapshot.query.order_by(AccountBalanceSnapshot.snapshot_date.desc(), AccountBalanceSnapshot.id.desc()).first()
    current_cycle_unpaid = money(sum(o.amount for o in due_before_next_payday))
    projected_balance_after_cycle = money((latest_balance.balance if latest_balance else 0) - current_cycle_unpaid)

    setup_steps = [
        {"label": "Check household settings", "done": bool(settings.first_payday), "url": url_for("main.settings_page")},
        {"label": "Add your first recurring bill", "done": RecurringBill.query.count() > 0, "url": url_for("main.new_bill")},
        {"label": "Add an income source", "done": IncomeSource.query.count() > 0, "url": url_for("main.new_income")},
        {"label": "Review your buckets", "done": Bucket.query.count() > 0, "url": url_for("main.buckets")},
    ]
    show_setup = (not settings.setup_checklist_dismissed) and (not all(step["done"] for step in setup_steps))
    dashboard_widgets, enabled_widgets = get_dashboard_widgets()

    return render_template(
        "dashboard.html",
        bill_fortnightly_total=bill_fortnightly_total,
        purchase_fortnightly_total=purchase_fortnightly_total,
        buffer_amount=buffer_amount,
        total_set_aside=total_set_aside,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        next_payday=next_payday,
        due_before_next_payday=due_before_next_payday,
        due_next_30_days=due_next_30_days,
        overdue=overdue,
        monthly_total=monthly_total,
        annual_total=annual_total,
        purchases=purchases,
        planned_purchase_fortnightly_amount=planned_purchase_fortnightly_amount,
        setup_steps=setup_steps,
        show_setup=show_setup,
        latest_balance=latest_balance,
        current_cycle_unpaid=current_cycle_unpaid,
        projected_balance_after_cycle=projected_balance_after_cycle,
        income_sources=income_sources,
        income_items=income_items,
        income_total=income_total,
        buckets=buckets,
        bucket_allocations=bucket_allocations,
        total_bucket_amount=total_bucket_amount,
        remaining_after_buckets=remaining_after_buckets,
        bills_bucket_total=bills_bucket_total,
        bills_and_purchases_bucket_total=bills_and_purchases_bucket_total,
        bills_bucket_delta=bills_bucket_delta,
        bills_bucket_status=bills_bucket_status,
        checklist_items=checklist_items,
        checklist_completed=checklist_completed,
        checklist_total=checklist_total,
        notifications=notifications,
        person_bucket_allocations=person_bucket_allocations,
        dashboard_widgets=dashboard_widgets,
        enabled_widgets=enabled_widgets,
    )


@main.route("/dashboard/dismiss-setup", methods=["GET", "POST"])
@login_required
def dismiss_setup_checklist():
    settings = get_settings()
    settings.setup_checklist_dismissed = True
    db.session.commit()
    flash("Setup checklist dismissed.", "success")
    return redirect(url_for("main.dashboard"))




@main.route("/dashboard/layout", methods=["GET", "POST"])
@login_required
def dashboard_layout():
    widgets, enabled_widgets = get_dashboard_widgets()
    if request.method == "POST":
        for widget in widgets:
            widget.enabled = request.form.get(f"enabled_{widget.id}") == "on"
            try:
                widget.sort_order = int(request.form.get(f"sort_order_{widget.id}", widget.sort_order))
            except ValueError:
                pass
            size = request.form.get(f"size_{widget.id}", widget.size)
            if size in ["small", "medium", "wide"]:
                widget.size = size
        db.session.commit()
        flash("Dashboard layout updated.", "success")
        return redirect(url_for("main.dashboard_layout"))
    return render_template("dashboard_layout.html", widgets=widgets)


@main.route("/dashboard/layout/reset", methods=["POST"])
@login_required
def reset_dashboard_layout():
    DashboardWidget.query.delete()
    db.session.commit()
    defaults = [
        ("setup_checklist", "Setup checklist", True, 5, "wide", "Initial setup prompts. Can be hidden once the app is configured."),
        ("set_aside_summary", "Set-aside summary", True, 10, "wide", "Main fortnightly set-aside number and components."),
        ("income_summary", "Income summary", True, 20, "medium", "Expected household income and remaining amount after bucket transfers."),
        ("bucket_summary", "Bucket summary", True, 30, "medium", "Combined household bucket totals."),
        ("per_person_contributions", "Individual contributions", True, 40, "wide", "How each person contributes to the buckets this cycle."),
        ("bills_bucket_health", "Bills bucket health", True, 45, "medium", "Shows whether the bills bucket covers the fortnightly bills requirement."),
        ("payday_checklist", "Payday checklist", True, 48, "medium", "Quick link to the transfer checklist for payday."),
        ("due_before_next_payday", "Due before next payday", True, 50, "wide", "Upcoming bills due before the next payday."),
        ("overdue_bills", "Overdue bills", True, 60, "wide", "Unpaid bills with due dates before today."),
        ("planned_purchases", "Planned purchases", False, 70, "medium", "Active planned purchases and quick-add saved amount."),
        ("account_balance", "Bills account balance", False, 80, "medium", "Latest manual bills account balance snapshot."),
        ("due_next_30_days", "Due in next 30 days", False, 90, "wide", "All unpaid bills due in the next 30 days."),
        ("recurring_totals", "Recurring totals", False, 100, "medium", "Monthly average and annual recurring bill totals."),
    ]
    for key, title, enabled, sort_order, size, description in defaults:
        db.session.add(DashboardWidget(widget_key=key, title=title, enabled=enabled, sort_order=sort_order, size=size, description=description))
    db.session.commit()
    flash("Dashboard layout reset.", "success")
    return redirect(url_for("main.dashboard_layout"))


@main.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    settings = get_settings()
    form = SettingsForm(obj=settings)
    if form.validate_on_submit():
        old_year = settings.budget_year
        form.populate_obj(settings)
        settings.first_payday = normalise_date_string(settings.first_payday)
        db.session.commit()
        # Regenerate all unpaid occurrences if the budget year changes.
        scope = "all_unpaid" if settings.budget_year != old_year else "future_unpaid"
        for bill in RecurringBill.query.all():
            regenerate_bill_occurrences(bill, scope=scope)
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("main.settings_page"))
    return render_template("settings.html", form=form)


@main.route("/bills")
@login_required
def bills():
    rows = RecurringBill.query.order_by(RecurringBill.name).all()
    return render_template("bills.html", bills=rows, annual_cost=annual_cost, fortnightly_bill_amount=fortnightly_bill_amount)


@main.route("/bills/new", methods=["GET", "POST"])
@login_required
def new_bill():
    form = RecurringBillForm()
    form.category_id.choices = category_choices("Bill")
    if form.validate_on_submit():
        bill = RecurringBill()
        form.populate_obj(bill)
        bill.start_date = normalise_date_string(bill.start_date)
        bill.end_date = normalise_date_string(bill.end_date) if bill.end_date else None
        new_category = get_or_create_category(form.new_category_name.data, "Bill")
        bill.category_id = new_category.id if new_category else (form.category_id.data or None)
        db.session.add(bill)
        db.session.flush()
        regenerate_bill_occurrences(bill, scope="all_unpaid")
        audit("add_bill", "RecurringBill", bill.name, f"Amount: {bill.amount}; frequency: {bill.frequency}")
        db.session.commit()
        flash("Bill added.", "success")
        return redirect(url_for("main.bills"))
    return render_template("bill_form.html", form=form, title="Add recurring bill", edit_mode=False)


@main.route("/bills/<int:bill_id>/edit", methods=["GET", "POST"])
@login_required
def edit_bill(bill_id):
    bill = db.session.get(RecurringBill, bill_id)
    form = RecurringBillForm(obj=bill)
    form.category_id.choices = category_choices("Bill")
    if request.method == "GET":
        form.category_id.data = bill.category_id or 0
    if form.validate_on_submit():
        scope = request.form.get("occurrence_update_scope", "future_unpaid")
        form.populate_obj(bill)
        bill.start_date = normalise_date_string(bill.start_date)
        bill.end_date = normalise_date_string(bill.end_date) if bill.end_date else None
        new_category = get_or_create_category(form.new_category_name.data, "Bill")
        bill.category_id = new_category.id if new_category else (form.category_id.data or None)
        regenerate_bill_occurrences(bill, scope=scope)
        audit("edit_bill", "RecurringBill", bill.name, f"Occurrence scope: {scope}")
        db.session.commit()
        flash("Bill updated.", "success")
        return redirect(url_for("main.bills"))
    return render_template("bill_form.html", form=form, title="Edit recurring bill", edit_mode=True)


@main.route("/bills/<int:bill_id>/delete", methods=["POST"])
@login_required
def delete_bill(bill_id):
    bill = db.session.get(RecurringBill, bill_id)
    audit("delete_bill", "RecurringBill", bill.name if bill else "Unknown", "Deleted recurring bill")
    db.session.delete(bill)
    db.session.commit()
    flash("Bill deleted.", "success")
    return redirect(url_for("main.bills"))


@main.route("/purchases")
@login_required
def purchases():
    rows = PlannedPurchase.query.order_by(PlannedPurchase.target_date).all()
    settings = get_settings()
    return render_template("purchases.html", purchases=rows, planned_purchase_fortnightly_amount=planned_purchase_fortnightly_amount, first_payday=settings.first_payday)


@main.route("/purchases/new", methods=["GET", "POST"])
@login_required
def new_purchase():
    form = PlannedPurchaseForm()
    form.category_id.choices = category_choices("Purchase")
    if form.validate_on_submit():
        purchase = PlannedPurchase()
        form.populate_obj(purchase)
        purchase.target_date = normalise_date_string(purchase.target_date)
        new_category = get_or_create_category(form.new_category_name.data, "Purchase")
        purchase.category_id = new_category.id if new_category else (form.category_id.data or None)
        db.session.add(purchase)
        db.session.commit()
        flash("Planned purchase added.", "success")
        return redirect(url_for("main.purchases"))
    return render_template("purchase_form.html", form=form, title="Add planned purchase")


@main.route("/purchases/<int:purchase_id>/edit", methods=["GET", "POST"])
@login_required
def edit_purchase(purchase_id):
    purchase = db.session.get(PlannedPurchase, purchase_id)
    form = PlannedPurchaseForm(obj=purchase)
    form.category_id.choices = category_choices("Purchase")
    if request.method == "GET":
        form.category_id.data = purchase.category_id or 0
    if form.validate_on_submit():
        form.populate_obj(purchase)
        purchase.target_date = normalise_date_string(purchase.target_date)
        new_category = get_or_create_category(form.new_category_name.data, "Purchase")
        purchase.category_id = new_category.id if new_category else (form.category_id.data or None)
        db.session.commit()
        flash("Planned purchase updated.", "success")
        return redirect(url_for("main.purchases"))
    return render_template("purchase_form.html", form=form, title="Edit planned purchase")


@main.route("/purchases/<int:purchase_id>/delete", methods=["POST"])
@login_required
def delete_purchase(purchase_id):
    purchase = db.session.get(PlannedPurchase, purchase_id)
    db.session.delete(purchase)
    db.session.commit()
    flash("Planned purchase deleted.", "success")
    return redirect(url_for("main.purchases"))


@main.route("/purchases/<int:purchase_id>/add-saved", methods=["POST"])
@login_required
def add_purchase_saved(purchase_id):
    purchase = db.session.get(PlannedPurchase, purchase_id)
    try:
        amount = float(request.form.get("amount", 0))
    except ValueError:
        amount = 0

    if amount <= 0:
        flash("Enter an amount greater than zero.", "warning")
        return redirect(request.referrer or url_for("main.purchases"))

    purchase.amount_saved = money(min(purchase.amount_saved + amount, purchase.target_amount))
    if purchase.amount_saved >= purchase.target_amount:
        flash("Saved amount updated. This target is now fully funded.", "success")
    else:
        flash("Saved amount updated.", "success")
    db.session.commit()
    return redirect(request.referrer or url_for("main.purchases"))


@main.route("/purchases/<int:purchase_id>/mark-purchased", methods=["POST"])
@login_required
def mark_purchase_purchased(purchase_id):
    purchase = db.session.get(PlannedPurchase, purchase_id)
    purchase.status = "Purchased"
    purchase.amount_saved = max(purchase.amount_saved, purchase.target_amount)
    db.session.commit()
    flash("Planned purchase marked as purchased.", "success")
    return redirect(request.referrer or url_for("main.purchases"))


@main.route("/calendar")
@login_required
def calendar_current():
    settings = get_settings()
    today = date.today()
    year = settings.budget_year or today.year
    month = today.month if year == today.year else 1
    return redirect(url_for("main.month_view", year=year, month=month, view="calendar"))


@main.route("/month/<int:year>/<int:month>")
@login_required
def month_view(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)

    selected_view = request.args.get("view", "calendar")
    if selected_view not in ["calendar", "list"]:
        selected_view = "calendar"

    occurrences = BillOccurrence.query.filter(
        BillOccurrence.due_date >= start.isoformat(),
        BillOccurrence.due_date <= end.isoformat(),
    ).order_by(BillOccurrence.due_date).all()

    income_sources = IncomeSource.query.filter_by(active=True).order_by(IncomeSource.owner_name, IncomeSource.name).all()
    income_events = []
    for source in income_sources:
        for pay_date in generate_income_dates(source, start, end):
            income_events.append({
                "date": pay_date,
                "type": "income",
                "title": f"{source.owner_name} - {source.name}",
                "amount": money(source.amount),
                "status": "Expected",
                "source": source,
            })

    bill_events = []
    for occurrence in occurrences:
        bill_events.append({
            "date": parse_date(occurrence.due_date),
            "type": "bill",
            "title": occurrence.bill.name,
            "amount": money(occurrence.amount),
            "status": occurrence.status,
            "occurrence": occurrence,
            "category": occurrence.bill.category.name if occurrence.bill.category else "Uncategorised",
        })

    month_events = sorted(bill_events + income_events, key=lambda item: (item["date"], 0 if item["type"] == "income" else 1, item["title"]))
    events_by_date = {}
    for event in month_events:
        events_by_date.setdefault(event["date"].isoformat(), []).append(event)

    calendar_weeks = []
    for week in Calendar(firstweekday=0).monthdatescalendar(year, month):
        calendar_weeks.append([
            {"date": day, "in_month": day.month == month, "events": events_by_date.get(day.isoformat(), [])}
            for day in week
        ])

    total = money(sum(o.amount for o in occurrences))
    paid = money(sum(o.amount for o in occurrences if o.status == "Paid"))
    unpaid = money(total - paid)
    income_total = money(sum(event["amount"] for event in income_events))

    return render_template(
        "month.html",
        year=year,
        month=month,
        month_name=month_name[month],
        selected_view=selected_view,
        occurrences=occurrences,
        month_events=month_events,
        calendar_weeks=calendar_weeks,
        total=total,
        paid=paid,
        unpaid=unpaid,
        income_total=income_total,
    )


@main.route("/occurrences/<int:occurrence_id>/paid", methods=["POST"])
@login_required
def mark_occurrence_paid(occurrence_id):
    occurrence = db.session.get(BillOccurrence, occurrence_id)
    occurrence.status = "Paid"
    occurrence.paid_date = date.today().isoformat()
    audit("mark_bill_paid", "BillOccurrence", occurrence.bill.name if occurrence.bill else "Bill", occurrence.due_date)
    db.session.commit()
    flash("Bill marked as paid.", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@main.route("/occurrences/<int:occurrence_id>/unpaid", methods=["POST"])
@login_required
def mark_occurrence_unpaid(occurrence_id):
    occurrence = db.session.get(BillOccurrence, occurrence_id)
    occurrence.status = "Upcoming"
    occurrence.paid_date = None
    audit("mark_bill_unpaid", "BillOccurrence", occurrence.bill.name if occurrence.bill else "Bill", occurrence.due_date)
    db.session.commit()
    flash("Bill marked as unpaid.", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@main.route("/occurrences/<int:occurrence_id>/skip", methods=["POST"])
@login_required
def skip_occurrence(occurrence_id):
    occurrence = db.session.get(BillOccurrence, occurrence_id)
    occurrence.status = "Skipped"
    occurrence.paid_date = None
    audit("skip_bill", "BillOccurrence", occurrence.bill.name if occurrence.bill else "Bill", occurrence.due_date)
    db.session.commit()
    flash("Bill occurrence skipped.", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@main.route("/pay-cycle")
@login_required
def pay_cycle():
    settings = get_settings()
    cycle_start, cycle_end, next_payday = current_pay_cycle(settings.first_payday)
    occurrences = BillOccurrence.query.filter(
        BillOccurrence.due_date >= cycle_start.isoformat(),
        BillOccurrence.due_date <= cycle_end.isoformat(),
    ).order_by(BillOccurrence.due_date).all()

    bills_due = money(sum(o.amount for o in occurrences if o.status != "Paid"))
    active_bills = RecurringBill.query.filter_by(active=True).all()
    purchases = PlannedPurchase.query.filter_by(status="Active").all()
    recurring_average = money(sum(fortnightly_bill_amount(b) for b in active_bills))
    purchase_average = money(sum(planned_purchase_fortnightly_amount(p, settings.first_payday) for p in purchases))
    total_average = money(recurring_average + purchase_average + settings.default_buffer_amount)
    income_sources = IncomeSource.query.filter_by(active=True).order_by(IncomeSource.next_pay_date, IncomeSource.name).all()
    income_items, income_total = income_for_cycle(income_sources, cycle_start, cycle_end)
    buckets = Bucket.query.filter_by(active=True).order_by(Bucket.sort_order, Bucket.name).all()
    bucket_allocations = calculate_bucket_allocations(buckets, income_total)
    person_bucket_allocations = calculate_person_bucket_allocations(income_items, buckets, income_total)

    return render_template(
        "pay_cycle.html",
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        next_payday=next_payday,
        occurrences=occurrences,
        bills_due=bills_due,
        recurring_average=recurring_average,
        purchase_average=purchase_average,
        total_average=total_average,
        income_items=income_items,
        income_total=income_total,
        bucket_allocations=bucket_allocations,
        person_bucket_allocations=person_bucket_allocations,
    )


@main.route("/income")
@login_required
def income_sources():
    rows = IncomeSource.query.order_by(IncomeSource.active.desc(), IncomeSource.next_pay_date, IncomeSource.name).all()
    return render_template("income.html", income_sources=rows)


@main.route("/income/new", methods=["GET", "POST"])
@login_required
def new_income():
    form = IncomeSourceForm()
    if form.validate_on_submit():
        income = IncomeSource()
        form.populate_obj(income)
        income.next_pay_date = normalise_date_string(income.next_pay_date)
        db.session.add(income)
        db.session.commit()
        flash("Income source added.", "success")
        return redirect(url_for("main.income_sources"))
    return render_template("income_form.html", form=form, title="Add income source")


@main.route("/income/<int:income_id>/edit", methods=["GET", "POST"])
@login_required
def edit_income(income_id):
    income = db.session.get(IncomeSource, income_id)
    form = IncomeSourceForm(obj=income)
    if form.validate_on_submit():
        form.populate_obj(income)
        income.next_pay_date = normalise_date_string(income.next_pay_date)
        db.session.commit()
        flash("Income source updated.", "success")
        return redirect(url_for("main.income_sources"))
    return render_template("income_form.html", form=form, title="Edit income source")


@main.route("/income/<int:income_id>/delete", methods=["POST"])
@login_required
def delete_income(income_id):
    income = db.session.get(IncomeSource, income_id)
    db.session.delete(income)
    db.session.commit()
    flash("Income source deleted.", "success")
    return redirect(url_for("main.income_sources"))


@main.route("/buckets", methods=["GET", "POST"])
@login_required
def buckets():
    enforce_single_remainder_bucket()
    form = BucketForm()
    if form.validate_on_submit():
        bucket = Bucket()
        if apply_bucket_form(bucket, form):
            db.session.add(bucket)
            db.session.flush()
            if bucket.cap_to_remaining:
                enforce_single_remainder_bucket(preferred_bucket=bucket)
            db.session.commit()
            flash("Bucket added.", "success")
            return redirect(url_for("main.buckets"))
    elif request.method == "GET":
        form.allocation_method.data = "percentage"

    rows = Bucket.query.order_by(Bucket.active.desc(), Bucket.sort_order, Bucket.name).all()
    active_buckets = [bucket for bucket in rows if bucket.active]
    total_percentage = money(sum(b.percentage for b in rows if b.active and b.fixed_amount in [None, ""]))

    settings = get_settings()
    cycle_start, cycle_end, next_payday = current_pay_cycle(settings.first_payday)
    income_sources = IncomeSource.query.filter_by(active=True).order_by(IncomeSource.next_pay_date, IncomeSource.owner_name, IncomeSource.name).all()
    income_items, income_total = income_for_cycle(income_sources, cycle_start, cycle_end)
    bucket_allocations = calculate_bucket_allocations(active_buckets, income_total)
    person_bucket_allocations = calculate_person_bucket_allocations(income_items, active_buckets, income_total)

    person_names = [person["person"] for person in person_bucket_allocations]
    bucket_contribution_rows = []
    for index, combined in enumerate(bucket_allocations):
        people = []
        for person in person_bucket_allocations:
            allocation = person["bucket_allocations"][index]
            people.append({
                "person": person["person"],
                "amount": allocation["rounded_amount"],
                "capped": allocation["capped"],
            })
        bucket_contribution_rows.append({
            "bucket": combined["bucket"],
            "target_label": combined["target_label"],
            "combined_amount": combined["rounded_amount"],
            "percentage_of_income": combined["percentage_of_income"],
            "capped": combined["capped"],
            "people": people,
        })

    bucket_total = money(sum(row["rounded_amount"] for row in bucket_allocations))
    remaining_after_buckets = money(income_total - bucket_total)

    return render_template(
        "buckets.html",
        form=form,
        buckets=rows,
        total_percentage=total_percentage,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        next_payday=next_payday,
        income_total=income_total,
        bucket_total=bucket_total,
        remaining_after_buckets=remaining_after_buckets,
        bucket_contribution_rows=bucket_contribution_rows,
        person_bucket_allocations=person_bucket_allocations,
        person_names=person_names,
    )


@main.route("/buckets/<int:bucket_id>/edit", methods=["GET", "POST"])
@login_required
def edit_bucket(bucket_id):
    bucket = db.session.get(Bucket, bucket_id)
    form = BucketForm(obj=bucket)
    if form.validate_on_submit():
        if apply_bucket_form(bucket, form):
            if bucket.cap_to_remaining:
                enforce_single_remainder_bucket(preferred_bucket=bucket)
            db.session.commit()
            flash("Bucket updated.", "success")
            return redirect(url_for("main.buckets"))
    elif request.method == "GET":
        prepare_bucket_form_for_display(form, bucket)
    return render_template("bucket_form.html", form=form, title="Edit bucket")


@main.route("/buckets/<int:bucket_id>/delete", methods=["POST"])
@login_required
def delete_bucket(bucket_id):
    bucket = db.session.get(Bucket, bucket_id)
    db.session.delete(bucket)
    db.session.commit()
    flash("Bucket deleted.", "success")
    return redirect(url_for("main.buckets"))


@main.route("/pay-split")
@login_required
def pay_split():
    settings = get_settings()
    cycle_start, cycle_end, next_payday = current_pay_cycle(settings.first_payday)
    income_sources = IncomeSource.query.filter_by(active=True).order_by(IncomeSource.next_pay_date, IncomeSource.name).all()
    income_items, income_total = income_for_cycle(income_sources, cycle_start, cycle_end)
    buckets = Bucket.query.filter_by(active=True).order_by(Bucket.sort_order, Bucket.name).all()
    bucket_allocations = calculate_bucket_allocations(buckets, income_total)
    person_bucket_allocations = calculate_person_bucket_allocations(income_items, buckets, income_total)
    recurring_average = money(sum(fortnightly_bill_amount(b) for b in RecurringBill.query.filter_by(active=True).all()))
    purchase_average = money(sum(planned_purchase_fortnightly_amount(p, settings.first_payday) for p in PlannedPurchase.query.filter_by(status="Active").all()))
    required_set_aside = money(recurring_average + purchase_average + settings.default_buffer_amount)
    bills_bucket_total = money(sum(row["rounded_amount"] for row in bucket_allocations if row["bucket"].bucket_type in ["Bills", "Planned purchases"]))
    bucket_total = money(sum(row["rounded_amount"] for row in bucket_allocations))
    remaining = money(income_total - bucket_total)
    shortfall = money(required_set_aside - bills_bucket_total)
    return render_template(
        "pay_split.html",
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        next_payday=next_payday,
        income_items=income_items,
        income_total=income_total,
        bucket_allocations=bucket_allocations,
        person_bucket_allocations=person_bucket_allocations,
        recurring_average=recurring_average,
        purchase_average=purchase_average,
        required_set_aside=required_set_aside,
        bills_bucket_total=bills_bucket_total,
        shortfall=shortfall,
        bucket_total=bucket_total,
        remaining=remaining,
    )


@main.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    form = CategoryForm()
    if form.validate_on_submit():
        category = Category()
        form.populate_obj(category)
        db.session.add(category)
        db.session.commit()
        flash("Category added.", "success")
        return redirect(url_for("main.categories"))
    rows = Category.query.order_by(Category.name).all()
    return render_template("categories.html", form=form, categories=rows)


@main.route("/account-balance", methods=["GET", "POST"])
@login_required
def account_balance():
    form = AccountBalanceForm(snapshot_date=date.today().isoformat())
    if form.validate_on_submit():
        snapshot = AccountBalanceSnapshot(
            snapshot_date=normalise_date_string(form.snapshot_date.data),
            balance=money(form.balance.data),
            notes=form.notes.data,
        )
        db.session.add(snapshot)
        db.session.commit()
        flash("Account balance saved.", "success")
        return redirect(url_for("main.account_balance"))
    rows = AccountBalanceSnapshot.query.order_by(AccountBalanceSnapshot.snapshot_date.desc(), AccountBalanceSnapshot.id.desc()).limit(20).all()
    return render_template("account_balance.html", form=form, snapshots=rows)



@main.route("/payday-checklist", methods=["GET", "POST"])
@login_required
def payday_checklist():
    settings = get_settings()
    cycle_start, cycle_end, next_payday = current_pay_cycle(settings.first_payday)
    income_sources = IncomeSource.query.filter_by(active=True).order_by(IncomeSource.next_pay_date, IncomeSource.name).all()
    income_items, income_total = income_for_cycle(income_sources, cycle_start, cycle_end)
    buckets = Bucket.query.filter_by(active=True).order_by(Bucket.sort_order, Bucket.name).all()
    bucket_allocations = calculate_bucket_allocations(buckets, income_total)
    person_bucket_allocations = calculate_person_bucket_allocations(income_items, buckets, income_total)
    checklist_items = ensure_payday_checklist_items(settings, cycle_start, income_items, person_bucket_allocations, bucket_allocations)

    if request.method == "POST":
        for item in checklist_items:
            completed = request.form.get(f"completed_{item.id}") == "on"
            if completed and not item.completed:
                item.completed_at = datetime.now().isoformat(timespec="seconds")
            elif not completed:
                item.completed_at = None
            item.completed = completed
        audit("update_payday_checklist", "PaydayChecklist", cycle_start.isoformat(), "Updated payday checklist")
        db.session.commit()
        flash("Payday checklist updated.", "success")
        return redirect(url_for("main.payday_checklist"))

    return render_template(
        "payday_checklist.html",
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        next_payday=next_payday,
        income_items=income_items,
        income_total=income_total,
        bucket_allocations=bucket_allocations,
        person_bucket_allocations=person_bucket_allocations,
        checklist_items=checklist_items,
    )


@main.route("/backup-restore", methods=["GET", "POST"])
@login_required
def backup_restore():
    db_path = get_database_path()
    last_backup = None
    backup_dir = os.path.join(current_app.instance_path, "backups")
    if os.path.isdir(backup_dir):
        backups = sorted([name for name in os.listdir(backup_dir) if name.endswith(".db")], reverse=True)
        last_backup = backups[0] if backups else None

    if request.method == "POST":
        upload = request.files.get("restore_file")
        confirm = request.form.get("confirm_restore") == "RESTORE"
        if not confirm:
            flash("Type RESTORE to confirm database restore.", "warning")
            return redirect(url_for("main.backup_restore"))
        if not upload or not upload.filename:
            flash("Choose a .db or .zip backup file.", "warning")
            return redirect(url_for("main.backup_restore"))
        try:
            os.makedirs(backup_dir, exist_ok=True)
            safety_backup = os.path.join(backup_dir, f"pre-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db")
            if os.path.exists(db_path):
                shutil.copy2(db_path, safety_backup)
            raw = upload.read()
            restore_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            restore_tmp.close()
            if upload.filename.lower().endswith(".zip"):
                with ZipFile(io.BytesIO(raw), "r") as zipf:
                    db_names = [name for name in zipf.namelist() if name.endswith(".db")]
                    if not db_names:
                        raise ValueError("No .db file found inside ZIP backup.")
                    with open(restore_tmp.name, "wb") as out:
                        out.write(zipf.read(db_names[0]))
            elif upload.filename.lower().endswith(".db"):
                with open(restore_tmp.name, "wb") as out:
                    out.write(raw)
            else:
                raise ValueError("Upload a .db or .zip backup file.")
            db.session.remove()
            db.engine.dispose()
            shutil.copy2(restore_tmp.name, db_path)
            flash("Database restored. Restart Project Solace now so all pages use the restored file.", "success")
        except Exception as exc:
            flash(f"Restore failed: {exc}", "danger")
        return redirect(url_for("main.backup_restore"))

    return render_template("backup_restore.html", db_path=db_path, last_backup=last_backup)


@main.route("/audit-log")
@login_required
def audit_log():
    rows = AuditLog.query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(200).all()
    return render_template("audit_log.html", rows=rows)


@main.route("/notifications", methods=["GET", "POST"])
@login_required
def notifications():
    settings_row = NotificationSetting.query.first()
    if not settings_row:
        settings_row = NotificationSetting()
        db.session.add(settings_row)
        db.session.commit()
    form = NotificationSettingsForm(obj=settings_row)
    if form.validate_on_submit():
        form.populate_obj(settings_row)
        db.session.commit()
        audit("update_notifications", "NotificationSetting", "Notifications", "Updated notification settings")
        flash("Notification settings saved.", "success")
        return redirect(url_for("main.notifications"))
    return render_template("notifications.html", form=form)

def bills_to_rows():
    rows = []
    for bill in RecurringBill.query.order_by(RecurringBill.name).all():
        rows.append({
            "name": bill.name,
            "amount": bill.amount,
            "frequency": bill.frequency,
            "due_day": bill.due_day,
            "due_month": bill.due_month or "",
            "start_date": bill.start_date,
            "end_date": bill.end_date or "",
            "category": bill.category.name if bill.category else "",
            "active": "yes" if bill.active else "no",
            "autopay": "yes" if bill.autopay else "no",
            "account_name": bill.account_name or "",
            "include_in_set_aside": "yes" if bill.include_in_set_aside else "no",
            "notes": bill.notes or "",
        })
    return rows


def purchases_to_rows():
    rows = []
    for purchase in PlannedPurchase.query.order_by(PlannedPurchase.target_date).all():
        rows.append({
            "name": purchase.name,
            "target_amount": purchase.target_amount,
            "amount_saved": purchase.amount_saved,
            "target_date": purchase.target_date,
            "category": purchase.category.name if purchase.category else "",
            "priority": purchase.priority,
            "status": purchase.status,
            "notes": purchase.notes or "",
        })
    return rows



def income_to_rows():
    rows = []
    for income in IncomeSource.query.order_by(IncomeSource.name).all():
        rows.append({
            "owner_name": getattr(income, "owner_name", "Household"),
            "name": income.name,
            "amount": income.amount,
            "frequency": income.frequency,
            "next_pay_date": income.next_pay_date,
            "active": "yes" if income.active else "no",
            "notes": income.notes or "",
        })
    return rows


def buckets_to_rows():
    rows = []
    for bucket in Bucket.query.order_by(Bucket.sort_order, Bucket.name).all():
        rows.append({
            "name": bucket.name,
            "percentage": bucket.percentage,
            "fixed_amount": bucket.fixed_amount if bucket.fixed_amount is not None else "",
            "rounding_increment": bucket.rounding_increment,
            "bucket_type": bucket.bucket_type,
            "cap_to_remaining": "yes" if getattr(bucket, "cap_to_remaining", False) else "no",
            "active": "yes" if bucket.active else "no",
            "sort_order": bucket.sort_order,
            "notes": bucket.notes or "",
        })
    return rows

def make_csv_response(filename, rows):
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@main.route("/data")
@login_required
def data_tools():
    return render_template("data_tools.html", import_preview=session.get("bill_import_preview") or [])


@main.route("/data/export/bills.csv")
@login_required
def export_bills_csv():
    return make_csv_response("project-solace-bills.csv", bills_to_rows())


@main.route("/data/export/purchases.csv")
@login_required
def export_purchases_csv():
    return make_csv_response("project-solace-planned-purchases.csv", purchases_to_rows())


@main.route("/data/export/income.csv")
@login_required
def export_income_csv():
    return make_csv_response("project-solace-income-sources.csv", income_to_rows())


@main.route("/data/export/buckets.csv")
@login_required
def export_buckets_csv():
    return make_csv_response("project-solace-buckets.csv", buckets_to_rows())


@main.route("/data/export/backup.xlsx")
@login_required
def export_backup_xlsx():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Bills"
    bill_rows = bills_to_rows()
    if bill_rows:
        ws.append(list(bill_rows[0].keys()))
        for row in bill_rows:
            ws.append(list(row.values()))
    ws2 = wb.create_sheet("Planned Purchases")
    purchase_rows = purchases_to_rows()
    if purchase_rows:
        ws2.append(list(purchase_rows[0].keys()))
        for row in purchase_rows:
            ws2.append(list(row.values()))
    ws3 = wb.create_sheet("Income Sources")
    income_rows = income_to_rows()
    if income_rows:
        ws3.append(list(income_rows[0].keys()))
        for row in income_rows:
            ws3.append(list(row.values()))
    ws4 = wb.create_sheet("Buckets")
    bucket_rows = buckets_to_rows()
    if bucket_rows:
        ws4.append(list(bucket_rows[0].keys()))
        for row in bucket_rows:
            ws4.append(list(row.values()))
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    wb.save(tmp.name)
    tmp.close()
    audit("export_backup_xlsx", "Backup", "Readable XLSX backup", "Downloaded readable backup")
    db.session.commit()
    return send_file(tmp.name, as_attachment=True, download_name="project-solace-backup.xlsx")


@main.route("/data/export/database.zip")
@login_required
def export_database_zip():
    db_path = current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()
    with ZipFile(tmp.name, "w", ZIP_DEFLATED) as zipf:
        if os.path.exists(db_path):
            zipf.write(db_path, arcname="solace.db")
    audit("export_database_zip", "Backup", "SQLite database ZIP", "Downloaded database backup")
    db.session.commit()
    return send_file(tmp.name, as_attachment=True, download_name="project-solace-database-backup.zip")


def read_uploaded_rows(file_storage):
    filename = file_storage.filename.lower()
    raw = file_storage.read()
    if filename.endswith(".csv"):
        text = raw.decode("utf-8-sig")
        return list(csv.DictReader(io.StringIO(text)))
    if filename.endswith(".xlsx"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(raw), data_only=True)
        ws = wb.active
        headers = [str(cell.value).strip().lower().replace(" ", "_") if cell.value is not None else "" for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            item = {}
            for idx, value in enumerate(row):
                if idx < len(headers) and headers[idx]:
                    item[headers[idx]] = value
            if any(value not in [None, ""] for value in item.values()):
                rows.append(item)
        return rows
    raise ValueError("Upload a CSV or XLSX file.")


def pick(row, *names, default=""):
    lowered = {str(k).lower().replace(" ", "_"): v for k, v in row.items()}
    for name in names:
        key = name.lower().replace(" ", "_")
        if key in lowered and lowered[key] not in [None, ""]:
            return lowered[key]
    return default



@main.route("/data/import/bills", methods=["POST"])
@login_required
def import_bills():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash("Choose a CSV or XLSX file first.", "warning")
        return redirect(url_for("main.data_tools"))
    try:
        raw_rows = read_uploaded_rows(upload)
        parsed_rows, error_count = parse_bill_import_rows(raw_rows)
        session["bill_import_preview"] = parsed_rows
        if error_count:
            flash(f"Import preview found {error_count} row(s) with errors. Fix the file or import only after reviewing.", "warning")
        else:
            flash(f"Import preview ready: {len(parsed_rows)} bill(s) detected.", "success")
        return redirect(url_for("main.data_tools"))
    except Exception as exc:
        flash(f"Import preview failed: {exc}", "danger")
        return redirect(url_for("main.data_tools"))


@main.route("/data/import/bills/confirm", methods=["POST"])
@login_required
def confirm_import_bills():
    parsed_rows = session.get("bill_import_preview") or []
    if not parsed_rows:
        flash("No bill import preview is waiting to be confirmed.", "warning")
        return redirect(url_for("main.data_tools"))
    imported = 0
    try:
        for row in parsed_rows:
            if row.get("errors"):
                continue
            category = get_or_create_category(row.get("category", ""), "Bill")
            bill = RecurringBill(
                name=row["name"],
                amount=float(row["amount"]),
                frequency=row["frequency"],
                due_day=int(row["due_day"]),
                due_month=row.get("due_month"),
                start_date=row["start_date"],
                end_date=row.get("end_date"),
                category_id=category.id if category else None,
                active=bool(row.get("active", True)),
                autopay=bool(row.get("autopay", False)),
                account_name=row.get("account_name", ""),
                include_in_set_aside=bool(row.get("include_in_set_aside", True)),
                notes=row.get("notes", ""),
            )
            db.session.add(bill)
            db.session.flush()
            regenerate_bill_occurrences(bill, scope="all_unpaid")
            imported += 1
        audit("import_bills", "RecurringBill", "Bill import", f"Imported {imported} bills from preview")
        db.session.commit()
        session.pop("bill_import_preview", None)
        flash(f"Imported {imported} recurring bills.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Import failed: {exc}", "danger")
    return redirect(url_for("main.data_tools"))


@main.route("/data/import/bills/cancel", methods=["POST"])
@login_required
def cancel_import_bills():
    session.pop("bill_import_preview", None)
    flash("Bill import preview cleared.", "info")
    return redirect(url_for("main.data_tools"))

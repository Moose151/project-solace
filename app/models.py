from datetime import date
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy database object used across the app.
db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="admin")
    active = db.Column(db.Boolean, default=True)
    display_name = db.Column(db.String(120), nullable=True)
    avatar_emoji = db.Column(db.String(10), nullable=True, default="🏠")

    @property
    def is_active(self):
        return self.active

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)


class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    household_name = db.Column(db.String(120), nullable=False, default="Project Solace")
    budget_year = db.Column(db.Integer, nullable=False, default=date.today().year)
    first_payday = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD for simple form handling.
    pay_frequency = db.Column(db.String(30), nullable=False, default="fortnightly")
    default_buffer_amount = db.Column(db.Float, nullable=False, default=0)
    currency_symbol = db.Column(db.String(5), nullable=False, default="$")
    theme = db.Column(db.String(20), nullable=False, default="Light")  # Light, Dark, Auto
    setup_checklist_dismissed = db.Column(db.Boolean, default=False)
    show_help_tips = db.Column(db.Boolean, default=True)
    payday_bill_handling = db.Column(db.String(20), nullable=False, default="new_cycle")  # new_cycle or previous_cycle


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    category_type = db.Column(db.String(20), nullable=False, default="Both")  # Bill, Purchase, Both
    active = db.Column(db.Boolean, default=True)
    fortnightly_budget = db.Column(db.Float, nullable=True)


class RecurringBill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(30), nullable=False)
    due_day = db.Column(db.Integer, nullable=False)
    due_month = db.Column(db.Integer, nullable=True)  # Used for yearly and six-monthly bills.
    start_date = db.Column(db.String(10), nullable=False)
    end_date = db.Column(db.String(10), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    active = db.Column(db.Boolean, default=True)
    autopay = db.Column(db.Boolean, default=False)
    account_name = db.Column(db.String(120), nullable=True)
    include_in_set_aside = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)

    category = db.relationship("Category")
    occurrences = db.relationship("BillOccurrence", back_populates="bill", cascade="all, delete-orphan")


class BillOccurrence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recurring_bill_id = db.Column(db.Integer, db.ForeignKey("recurring_bill.id"), nullable=False, index=True)
    due_date = db.Column(db.String(10), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Upcoming", index=True)  # Upcoming, Paid, Skipped
    paid_date = db.Column(db.String(10), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    bill = db.relationship("RecurringBill", back_populates="occurrences")


class PlannedPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    amount_saved = db.Column(db.Float, nullable=False, default=0)
    target_date = db.Column(db.String(10), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    status = db.Column(db.String(20), nullable=False, default="Active")  # Active, Purchased, Paused, Cancelled
    purchase_scope = db.Column(db.String(20), nullable=False, default="Shared")  # Shared or Individual
    owner_name = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    category = db.relationship("Category")


class AccountBalanceSnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    snapshot_date = db.Column(db.String(10), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)


class IncomeSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_name = db.Column(db.String(120), nullable=False, default="Household")
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(30), nullable=False, default="Fortnightly")
    next_pay_date = db.Column(db.String(10), nullable=False)
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text, nullable=True)

    # Shared income fields.
    # income_scope: "Individual" (default) or "Shared". Shared income is not
    # attributed to any person's contribution breakdown; it is added to the
    # household pool after per-person splits are calculated.
    income_scope = db.Column(db.String(20), nullable=False, default="Individual")
    # allocation_mode: how shared income is distributed across buckets.
    #   "standard"  — flows through the normal bucket percentage/fixed math
    #   "lump"      — full amount goes to one nominated bucket
    #   "custom"    — split across nominated buckets using custom percentages;
    #                 any remainder goes to the bucket flagged is_remainder=True
    allocation_mode = db.Column(db.String(20), nullable=False, default="standard")
    # lump_bucket_id: used only when allocation_mode == "lump"
    lump_bucket_id = db.Column(db.Integer, db.ForeignKey("bucket.id"), nullable=True)

    lump_bucket = db.relationship("Bucket", foreign_keys=[lump_bucket_id])
    shared_allocations = db.relationship(
        "SharedIncomeAllocation",
        back_populates="income_source",
        cascade="all, delete-orphan",
        order_by="SharedIncomeAllocation.sort_order",
    )


class SharedIncomeAllocation(db.Model):
    """Custom bucket split for a shared income source in 'custom' allocation mode.

    Each row says "send <percentage>% of this income source's amount to <bucket>".
    Exactly one row per income source may have is_remainder=True; that bucket
    receives whatever is left after all other percentages are applied, matching
    the cap_to_remaining pattern used in the standard bucket engine.
    """
    id = db.Column(db.Integer, primary_key=True)
    income_source_id = db.Column(db.Integer, db.ForeignKey("income_source.id"), nullable=False, index=True)
    bucket_id = db.Column(db.Integer, db.ForeignKey("bucket.id"), nullable=False)
    percentage = db.Column(db.Float, nullable=False, default=0)
    is_remainder = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    income_source = db.relationship("IncomeSource", back_populates="shared_allocations")
    bucket = db.relationship("Bucket")


class Bucket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    percentage = db.Column(db.Float, nullable=False, default=0)
    fixed_amount = db.Column(db.Float, nullable=True)
    rounding_increment = db.Column(db.Integer, nullable=False, default=10)
    cap_to_remaining = db.Column(db.Boolean, default=False)
    bucket_type = db.Column(db.String(30), nullable=False, default="Other")  # Bills, Savings, Spending, Planned purchases, Other
    active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)


class DashboardWidget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    widget_key = db.Column(db.String(80), unique=True, nullable=False)
    title = db.Column(db.String(120), nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    size = db.Column(db.String(20), nullable=False, default="medium")  # small, medium, wide
    description = db.Column(db.String(255), nullable=True)


class PaydayChecklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cycle_start = db.Column(db.String(10), nullable=False, index=True)
    item_key = db.Column(db.String(120), nullable=False)
    label = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.String(25), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class PaydayChecklistPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_key = db.Column(db.String(120), unique=True, nullable=False)
    label = db.Column(db.String(255), nullable=False)
    hidden = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(120), nullable=True)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.String(25), nullable=False, index=True)
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(80), nullable=True)
    entity_name = db.Column(db.String(160), nullable=True)
    details = db.Column(db.Text, nullable=True)


# Notification webhook URLs/tokens are stored in plaintext for this local, self-hosted household tool.
# Do not store external email/API credentials here without revisiting secret storage.
class NotificationSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False)
    dashboard_reminders = db.Column(db.Boolean, default=True)
    due_soon_days = db.Column(db.Integer, nullable=False, default=3)
    provider = db.Column(db.String(30), nullable=False, default="None")  # None, ntfy, Gotify/Webhook
    webhook_url = db.Column(db.String(500), nullable=True)
    token = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)


class CycleCloseout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cycle_start = db.Column(db.String(10), unique=True, nullable=False)
    cycle_end = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Open")  # Open, Closed
    closed_at = db.Column(db.String(25), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    actual_income = db.Column(db.Float, nullable=True)

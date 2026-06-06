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

    @property
    def is_active(self):
        return self.active


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


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    category_type = db.Column(db.String(20), nullable=False, default="Both")  # Bill, Purchase, Both
    active = db.Column(db.Boolean, default=True)


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
    recurring_bill_id = db.Column(db.Integer, db.ForeignKey("recurring_bill.id"), nullable=False)
    due_date = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Upcoming")  # Upcoming, Paid, Skipped
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

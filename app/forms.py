import re

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, FloatField, IntegerField, SelectField,
    BooleanField, TextAreaField, SubmitField
)
from wtforms.validators import DataRequired, NumberRange, Optional, Length, ValidationError

from .budget_engine import parse_date

MAX_MONEY_AMOUNT = 1_000_000


def valid_date(form, field):
    """Validate date strings before route logic runs.

    Solace accepts ISO dates and common Australian date formats. Keeping this
    validator at the form layer prevents bad dates from becoming 500 errors.
    """
    if field.data in [None, ""]:
        return
    try:
        parse_date(field.data)
    except ValueError:
        raise ValidationError("Enter a valid date, e.g. DD/MM/YYYY or YYYY-MM-DD.")


def valid_web_url(form, field):
    """Validate optional webhook URLs for future notification providers."""
    if not field.data:
        return
    if not re.match(r"^https?://", field.data.strip(), flags=re.IGNORECASE):
        raise ValidationError("Enter a valid URL starting with http:// or https://.")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class SettingsForm(FlaskForm):
    household_name = StringField("Household name", validators=[DataRequired(), Length(max=120)])
    budget_year = IntegerField("Budget year", validators=[DataRequired(), NumberRange(min=2020, max=2100)])
    first_payday = StringField("First payday", validators=[DataRequired(), valid_date], description="YYYY-MM-DD or DD/MM/YYYY")
    pay_frequency = SelectField("Pay frequency", choices=[("fortnightly", "Fortnightly")], description="Solace currently supports fortnightly household pay cycles.")
    default_buffer_amount = FloatField("Default buffer amount", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)])
    currency_symbol = StringField("Currency symbol", validators=[DataRequired(), Length(max=5)])
    theme = SelectField("Theme", choices=[("Light", "Light"), ("Dark", "Dark"), ("Auto", "Auto")])
    show_help_tips = BooleanField("Show help tips", default=True, description="Shows small ? icons beside optional guidance. Important warnings are still shown even when this is off.")
    payday_bill_handling = SelectField("Bills due on payday belong to", choices=[("new_cycle", "New pay cycle"), ("previous_cycle", "Previous pay cycle")], description="Choose whether a bill due on payday should appear in the cycle that just ended or the new cycle starting on payday.")
    submit = SubmitField("Save settings")


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(max=80)])
    category_type = SelectField("Category type", choices=[("Bill", "Bill"), ("Purchase", "Purchase"), ("Both", "Both")])
    active = BooleanField("Active", default=True)
    submit = SubmitField("Save category")


class RecurringBillForm(FlaskForm):
    name = StringField("Bill name", validators=[DataRequired(), Length(max=120)])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01, max=MAX_MONEY_AMOUNT)])
    frequency = SelectField(
        "Frequency",
        choices=[
            ("Weekly", "Weekly"),
            ("Fortnightly", "Fortnightly"),
            ("Monthly", "Monthly"),
            ("Quarterly", "Quarterly"),
            ("Six-monthly", "Six-monthly"),
            ("Yearly", "Yearly"),
        ],
    )
    first_due_date = StringField(
        "First due date",
        validators=[DataRequired(), valid_date],
        description="The first date this bill comes out. Solace uses this to work out the day and repeat pattern."
    )
    # Legacy/generated fields are retained for model compatibility but are not
    # rendered in the normal UI. apply_bill_form derives them from first_due_date.
    due_day = IntegerField("Generated due day", validators=[Optional(), NumberRange(min=1, max=31)])
    due_month = IntegerField("Generated due month", validators=[Optional(), NumberRange(min=1, max=12)])
    start_date = StringField("Generated start date", validators=[Optional(), valid_date])
    end_date = StringField("Stop after date", validators=[Optional(), valid_date], description="Optional. Leave blank unless the bill should stop after a date.")
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    new_category_name = StringField("New category", validators=[Optional(), Length(max=80)], description="Optional. Creates a new bill category and uses it for this bill.")
    active = BooleanField("Active", default=True)
    autopay = BooleanField("Autopay")
    account_name = StringField("Account paid from", validators=[Optional(), Length(max=120)])
    include_in_set_aside = BooleanField("Include in set-aside", default=True)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save bill")


class PlannedPurchaseForm(FlaskForm):
    name = StringField("Purchase name", validators=[DataRequired(), Length(max=120)])
    target_amount = FloatField("Target amount", validators=[DataRequired(), NumberRange(min=0.01, max=MAX_MONEY_AMOUNT)])
    amount_saved = FloatField("Amount already saved", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)], default=0)
    target_date = StringField("Target date", validators=[DataRequired(), valid_date], description="YYYY-MM-DD or DD/MM/YYYY")
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    new_category_name = StringField("New category", validators=[Optional(), Length(max=80)], description="Optional. Creates a new planned purchase category and uses it for this purchase.")
    purchase_scope = SelectField(
        "Purchase type",
        choices=[("Shared", "Shared purchase"), ("Individual", "Individual purchase")],
        default="Shared",
        description="Shared purchases are saved for by the household. Individual purchases are funded from one person's individual spending."
    )
    owner_name = SelectField("Person", choices=[], validators=[Optional()], description="Only used for individual planned purchases.")
    priority = SelectField("Priority", choices=[("Low", "Low"), ("Medium", "Medium"), ("High", "High")])
    status = SelectField("Status", choices=[("Active", "Active"), ("Purchased", "Purchased"), ("Paused", "Paused"), ("Cancelled", "Cancelled")])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save purchase")


class AccountBalanceForm(FlaskForm):
    snapshot_date = StringField("Balance date", validators=[DataRequired(), valid_date], description="YYYY-MM-DD or DD/MM/YYYY")
    balance = FloatField("Bills/set-aside account balance", validators=[DataRequired(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save balance")


class IncomeSourceForm(FlaskForm):
    owner_name = StringField("Person", validators=[DataRequired(), Length(max=120)], description="Who receives this pay, e.g. Nick or partner.")
    name = StringField("Income source name", validators=[DataRequired(), Length(max=120)])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01, max=MAX_MONEY_AMOUNT)])
    frequency = SelectField("Frequency", choices=[("Fortnightly", "Fortnightly")], description="Solace currently supports fortnightly income schedules.")
    next_pay_date = StringField(
        "Known pay date",
        validators=[DataRequired(), valid_date],
        description="Enter any known payday for this income. It can be in the past; Solace uses it as the fortnightly schedule anchor."
    )
    active = BooleanField("Active", default=True)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save income source")


class BucketForm(FlaskForm):
    name = StringField("Bucket name", validators=[DataRequired(), Length(max=120)])
    allocation_method = SelectField(
        "Bucket amount type",
        choices=[("percentage", "Percentage of income"), ("fixed", "Fixed household amount")],
        default="percentage",
        description="Choose one. Percentage uses each person's own income. Fixed splits the household amount by income share."
    )
    percentage = FloatField("Percentage of income", validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    fixed_amount = FloatField("Fixed household amount", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)])
    rounding_increment = SelectField(
        "Round transfer to nearest",
        coerce=int,
        choices=[(1, "$1"), (5, "$5"), (10, "$10"), (20, "$20"), (50, "$50"), (100, "$100")],
        default=10,
    )
    cap_to_remaining = BooleanField(
        "Use remainder for this bucket",
        default=False,
        description="Only one bucket can use this. It takes only what remains after earlier buckets are allocated."
    )
    bucket_type = SelectField(
        "Bucket type",
        choices=[
            ("Bills", "Bills"),
            ("Savings", "Savings"),
            ("Spending", "Spending"),
            ("Planned purchases", "Planned purchases"),
            ("Other", "Other"),
        ],
    )
    active = BooleanField("Active", default=True)
    sort_order = IntegerField("Sort order", validators=[Optional()], default=0)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save bucket")


class NotificationSettingsForm(FlaskForm):
    enabled = BooleanField("Enable external notifications")
    dashboard_reminders = BooleanField("Show dashboard reminders", default=True)
    due_soon_days = IntegerField("Due-soon warning days", validators=[DataRequired(), NumberRange(min=1, max=60)], default=3)
    provider = SelectField("Notification provider", choices=[("None", "None"), ("ntfy", "ntfy"), ("webhook", "Gotify / generic webhook")])
    webhook_url = StringField("Webhook / ntfy URL", validators=[Optional(), Length(max=500), valid_web_url])
    token = StringField("Token", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save notification settings")


class CycleCloseoutForm(FlaskForm):
    notes = TextAreaField("Closeout notes", validators=[Optional()])
    submit = SubmitField("Close cycle")

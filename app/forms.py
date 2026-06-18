import re

from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, FloatField, IntegerField, SelectField,
    BooleanField, TextAreaField, SubmitField
)
from wtforms.validators import DataRequired, NumberRange, Optional, Length, ValidationError

from .budget_engine import parse_date

MAX_MONEY_AMOUNT = 1_000_000

DATE_INPUT_KWARGS = {"type": "date", "autocomplete": "off"}
MONEY_INPUT_KWARGS = {"inputmode": "decimal", "step": "0.01", "autocomplete": "off"}
NUMERIC_INPUT_KWARGS = {"inputmode": "numeric", "autocomplete": "off"}


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
    budget_year = IntegerField("Budget year", validators=[DataRequired(), NumberRange(min=2020, max=2100)], render_kw=NUMERIC_INPUT_KWARGS)
    first_payday = StringField("First payday", validators=[DataRequired(), valid_date], description="Use the calendar picker or enter YYYY-MM-DD.", render_kw=DATE_INPUT_KWARGS)
    pay_frequency = SelectField("Pay frequency", choices=[("fortnightly", "Fortnightly"), ("weekly", "Weekly")], description="Household pay cycle frequency.")
    default_buffer_amount = FloatField("Default buffer amount", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)], render_kw=MONEY_INPUT_KWARGS)
    currency_symbol = StringField("Currency symbol", validators=[DataRequired(), Length(max=5)])
    theme = SelectField("Theme", choices=[("Light", "Light"), ("Dark", "Dark"), ("Auto", "Auto")])
    show_help_tips = BooleanField("Show help tips", default=True, description="Shows small ? icons beside optional guidance. Important warnings are still shown even when this is off.")
    payday_bill_handling = SelectField("Bills due on payday belong to", choices=[("new_cycle", "New pay cycle"), ("previous_cycle", "Previous pay cycle")], description="Choose whether a bill due on payday should appear in the cycle that just ended or the new cycle starting on payday.")
    submit = SubmitField("Save settings")


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(max=80)])
    category_type = SelectField("Category type", choices=[("Bill", "Bill"), ("Purchase", "Purchase"), ("Both", "Both")])
    active = BooleanField("Active", default=True)
    fortnightly_budget = FloatField("Fortnightly budget (optional)", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)], render_kw={**MONEY_INPUT_KWARGS, "placeholder": "e.g. 200.00"})
    submit = SubmitField("Save category")


class RecurringBillForm(FlaskForm):
    name = StringField("Bill name", validators=[DataRequired(), Length(max=120)])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01, max=MAX_MONEY_AMOUNT)], render_kw=MONEY_INPUT_KWARGS)
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
        description="Use the calendar picker. This is the first date this bill comes out.",
        render_kw=DATE_INPUT_KWARGS,
    )
    # Legacy/generated fields are retained for model compatibility but are not
    # rendered in the normal UI. apply_bill_form derives them from first_due_date.
    due_day = IntegerField("Generated due day", validators=[Optional(), NumberRange(min=1, max=31)], render_kw=NUMERIC_INPUT_KWARGS)
    due_month = IntegerField("Generated due month", validators=[Optional(), NumberRange(min=1, max=12)], render_kw=NUMERIC_INPUT_KWARGS)
    start_date = StringField("Generated start date", validators=[Optional(), valid_date], render_kw=DATE_INPUT_KWARGS)
    end_date = StringField("Stop after date", validators=[Optional(), valid_date], description="Optional. Leave blank unless the bill should stop after a date.", render_kw=DATE_INPUT_KWARGS)
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
    target_amount = FloatField("Target amount", validators=[DataRequired(), NumberRange(min=0.01, max=MAX_MONEY_AMOUNT)], render_kw=MONEY_INPUT_KWARGS)
    amount_saved = FloatField("Amount already saved", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)], default=0, render_kw=MONEY_INPUT_KWARGS)
    target_date = StringField("Target date", validators=[DataRequired(), valid_date], description="Use the calendar picker or enter YYYY-MM-DD.", render_kw=DATE_INPUT_KWARGS)
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
    snapshot_date = StringField("Balance date", validators=[DataRequired(), valid_date], description="Use the calendar picker or enter YYYY-MM-DD.", render_kw=DATE_INPUT_KWARGS)
    balance = FloatField("Bills/set-aside account balance", validators=[DataRequired(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)], render_kw=MONEY_INPUT_KWARGS)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save balance")


class IncomeSourceForm(FlaskForm):
    income_scope = SelectField(
        "Income type",
        choices=[("Individual", "Individual — belongs to one person"), ("Shared", "Shared — household income (rent, interest, etc.)")],
        default="Individual",
        description="Individual income is attributed to a person's contribution breakdown. Shared income is added to the household pool after per-person splits are calculated.",
    )
    owner_name = StringField("Person", validators=[Optional(), Length(max=120)], description="Who receives this pay, e.g. Nick or partner. Not used for shared income.")
    name = StringField("Income source name", validators=[DataRequired(), Length(max=120)])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01, max=MAX_MONEY_AMOUNT)], render_kw=MONEY_INPUT_KWARGS)
    frequency = SelectField(
        "Frequency",
        choices=[("Fortnightly", "Fortnightly"), ("Weekly", "Weekly")],
        description="How often this income is received.",
    )
    next_pay_date = StringField(
        "Known pay date",
        validators=[DataRequired(), valid_date],
        description="Use the calendar picker. This can be a past date; Solace uses it as the schedule anchor.",
        render_kw=DATE_INPUT_KWARGS,
    )
    active = BooleanField("Active", default=True)
    notes = TextAreaField("Notes", validators=[Optional()])

    # Shared income allocation fields. These are only relevant when
    # income_scope == "Shared". The template shows/hides them via JS.
    allocation_mode = SelectField(
        "Allocation method",
        choices=[
            ("standard", "Standard — flows through normal bucket percentages"),
            ("lump", "Lump sum — full amount into one bucket"),
            ("custom", "Custom split — define percentages per bucket"),
        ],
        default="standard",
        description="How this shared income is distributed across buckets.",
    )
    lump_bucket_id = SelectField("Destination bucket", coerce=int, validators=[Optional()], description="Used when allocation method is 'Lump sum'.")

    submit = SubmitField("Save income source")


class SharedIncomeAllocationForm(FlaskForm):
    """Inline form for one custom allocation row on the income edit page."""
    bucket_id = SelectField("Bucket", coerce=int, validators=[DataRequired()])
    percentage = FloatField("Percentage", validators=[Optional(), NumberRange(min=0, max=100)], default=0, render_kw=MONEY_INPUT_KWARGS)
    is_remainder = BooleanField("Use as remainder bucket", default=False, description="This bucket receives whatever is left after all other percentages are applied.")
    sort_order = IntegerField("Order", validators=[Optional()], default=0, render_kw=NUMERIC_INPUT_KWARGS)
    submit = SubmitField("Save allocation")


class BucketForm(FlaskForm):
    name = StringField("Bucket name", validators=[DataRequired(), Length(max=120)])
    allocation_method = SelectField(
        "Bucket amount type",
        choices=[("percentage", "Percentage of income"), ("fixed", "Fixed household amount")],
        default="percentage",
        description="Choose one. Percentage uses each person's own income. Fixed splits the household amount by income share."
    )
    percentage = FloatField("Percentage of income", validators=[Optional(), NumberRange(min=0, max=100)], default=0, render_kw=MONEY_INPUT_KWARGS)
    fixed_amount = FloatField("Fixed household amount", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)], render_kw=MONEY_INPUT_KWARGS)
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
    sort_order = IntegerField("Sort order", validators=[Optional()], default=0, render_kw=NUMERIC_INPUT_KWARGS)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save bucket")


class NotificationSettingsForm(FlaskForm):
    enabled = BooleanField("Enable external notifications")
    dashboard_reminders = BooleanField("Show dashboard reminders", default=True)
    due_soon_days = IntegerField("Due-soon warning days", validators=[DataRequired(), NumberRange(min=1, max=60)], default=3, render_kw=NUMERIC_INPUT_KWARGS)
    provider = SelectField("Notification provider", choices=[("None", "None"), ("ntfy", "ntfy"), ("webhook", "Gotify / generic webhook")])
    webhook_url = StringField("Webhook / ntfy URL", validators=[Optional(), Length(max=500), valid_web_url])
    token = StringField("Token", validators=[Optional(), Length(max=255)])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save notification settings")


class CycleCloseoutForm(FlaskForm):
    actual_income = FloatField("Actual income received", validators=[Optional(), NumberRange(min=0, max=MAX_MONEY_AMOUNT)], render_kw={**MONEY_INPUT_KWARGS, "placeholder": "Leave blank if same as expected"})
    notes = TextAreaField("Closeout notes", validators=[Optional()])
    submit = SubmitField("Close cycle")

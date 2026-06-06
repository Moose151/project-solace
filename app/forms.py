from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, FloatField, IntegerField, SelectField,
    BooleanField, TextAreaField, SubmitField
)
from wtforms.validators import DataRequired, NumberRange, Optional, Length


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class SettingsForm(FlaskForm):
    household_name = StringField("Household name", validators=[DataRequired(), Length(max=120)])
    budget_year = IntegerField("Budget year", validators=[DataRequired(), NumberRange(min=2020, max=2100)])
    first_payday = StringField("First payday", validators=[DataRequired()], description="YYYY-MM-DD or DD/MM/YYYY")
    pay_frequency = SelectField("Pay frequency", choices=[("fortnightly", "Fortnightly")])
    default_buffer_amount = FloatField("Default buffer amount", validators=[Optional(), NumberRange(min=0)])
    currency_symbol = StringField("Currency symbol", validators=[DataRequired(), Length(max=5)])
    theme = SelectField("Theme", choices=[("Light", "Light"), ("Dark", "Dark"), ("Auto", "Auto")])
    submit = SubmitField("Save settings")


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(max=80)])
    category_type = SelectField("Category type", choices=[("Bill", "Bill"), ("Purchase", "Purchase"), ("Both", "Both")])
    active = BooleanField("Active", default=True)
    submit = SubmitField("Save category")


class RecurringBillForm(FlaskForm):
    name = StringField("Bill name", validators=[DataRequired(), Length(max=120)])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01)])
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
    due_day = IntegerField("Due day", validators=[DataRequired(), NumberRange(min=1, max=31)])
    due_month = IntegerField("Due month", validators=[Optional(), NumberRange(min=1, max=12)], description="Use for yearly/six-monthly bills")
    start_date = StringField("Start date", validators=[DataRequired()], description="YYYY-MM-DD or DD/MM/YYYY")
    end_date = StringField("End date", validators=[Optional()], description="YYYY-MM-DD or DD/MM/YYYY, optional")
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    active = BooleanField("Active", default=True)
    autopay = BooleanField("Autopay")
    account_name = StringField("Account paid from", validators=[Optional(), Length(max=120)])
    include_in_set_aside = BooleanField("Include in set-aside", default=True)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save bill")


class PlannedPurchaseForm(FlaskForm):
    name = StringField("Purchase name", validators=[DataRequired(), Length(max=120)])
    target_amount = FloatField("Target amount", validators=[DataRequired(), NumberRange(min=0.01)])
    amount_saved = FloatField("Amount already saved", validators=[Optional(), NumberRange(min=0)], default=0)
    target_date = StringField("Target date", validators=[DataRequired()], description="YYYY-MM-DD or DD/MM/YYYY")
    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    priority = SelectField("Priority", choices=[("Low", "Low"), ("Medium", "Medium"), ("High", "High")])
    status = SelectField("Status", choices=[("Active", "Active"), ("Purchased", "Purchased"), ("Paused", "Paused"), ("Cancelled", "Cancelled")])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save purchase")


class AccountBalanceForm(FlaskForm):
    snapshot_date = StringField("Balance date", validators=[DataRequired()], description="YYYY-MM-DD or DD/MM/YYYY")
    balance = FloatField("Bills/set-aside account balance", validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save balance")


class IncomeSourceForm(FlaskForm):
    name = StringField("Income source name", validators=[DataRequired(), Length(max=120)])
    amount = FloatField("Amount", validators=[DataRequired(), NumberRange(min=0.01)])
    frequency = SelectField("Frequency", choices=[("Fortnightly", "Fortnightly")])
    next_pay_date = StringField("Next pay date", validators=[DataRequired()], description="YYYY-MM-DD or DD/MM/YYYY")
    active = BooleanField("Active", default=True)
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save income source")


class BucketForm(FlaskForm):
    name = StringField("Bucket name", validators=[DataRequired(), Length(max=120)])
    percentage = FloatField("Percentage of household pay", validators=[DataRequired(), NumberRange(min=0, max=100)])
    fixed_amount = FloatField("Optional fixed amount", validators=[Optional(), NumberRange(min=0)], description="Overrides percentage if entered")
    rounding_increment = SelectField(
        "Round transfer to nearest",
        coerce=int,
        choices=[(1, "$1"), (5, "$5"), (10, "$10"), (20, "$20"), (50, "$50"), (100, "$100")],
        default=10,
    )
    cap_to_remaining = BooleanField(
        "Use remainder if this bucket would make the pay split negative",
        default=False,
        description="Caps this bucket to whatever income remains after earlier buckets are allocated."
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

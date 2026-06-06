import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash
from sqlalchemy import text

from .models import db, User, Settings, Category, Bucket, IncomeSource, DashboardWidget

login_manager = LoginManager()
login_manager.login_view = "main.login"
csrf = CSRFProtect()


def create_app():
    """Create and configure the Project Solace Flask app."""
    app = Flask(__name__, instance_relative_config=True)

    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(app.instance_path, "solace.db"),
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        apply_lightweight_migrations()
        seed_default_data()
        seed_dashboard_widgets()

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def column_exists(table_name, column_name):
    """Check for a column in SQLite so existing installs can be upgraded."""
    rows = db.session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return any(row[1] == column_name for row in rows)


def apply_lightweight_migrations():
    """Apply simple SQLite ALTER TABLE migrations for MVP development.

    This avoids needing Alembic while the project is still small. For a mature
    app, replace this with Flask-Migrate/Alembic migrations.
    """
    if not column_exists("settings", "theme"):
        db.session.execute(text("ALTER TABLE settings ADD COLUMN theme VARCHAR(20) NOT NULL DEFAULT 'Light'"))

    if not column_exists("settings", "setup_checklist_dismissed"):
        db.session.execute(text("ALTER TABLE settings ADD COLUMN setup_checklist_dismissed BOOLEAN NOT NULL DEFAULT 0"))

    if not column_exists("bucket", "cap_to_remaining"):
        db.session.execute(text("ALTER TABLE bucket ADD COLUMN cap_to_remaining BOOLEAN NOT NULL DEFAULT 0"))

    if not column_exists("income_source", "owner_name"):
        db.session.execute(text("ALTER TABLE income_source ADD COLUMN owner_name VARCHAR(120) NOT NULL DEFAULT 'Household'"))

    if not Bucket.query.first():
        starter_buckets = [
            ("Bills", 25, 10, "Bills", 10),
            ("Savings", 20, 10, "Savings", 20),
            ("Shared spending", 45, 10, "Spending", 30),
            ("Individual spending", 10, 10, "Other", 40),
        ]
        for name, percentage, rounding_increment, bucket_type, sort_order in starter_buckets:
            db.session.add(Bucket(
                name=name,
                percentage=percentage,
                rounding_increment=rounding_increment,
                bucket_type=bucket_type,
                sort_order=sort_order,
                active=True,
            ))

    capped_buckets = Bucket.query.filter(Bucket.cap_to_remaining.is_(True)).order_by(Bucket.sort_order, Bucket.name).all()
    for bucket in capped_buckets[1:]:
        bucket.cap_to_remaining = False

    db.session.commit()



def seed_dashboard_widgets():
    """Create default dashboard widgets for modular dashboard layout."""
    defaults = [
        ("setup_checklist", "Setup checklist", True, 5, "wide", "Initial setup prompts. Can be hidden once the app is configured."),
        ("set_aside_summary", "Set-aside summary", True, 10, "wide", "Main fortnightly set-aside number and components."),
        ("income_summary", "Income summary", True, 20, "medium", "Expected household income and remaining amount after bucket transfers."),
        ("bucket_summary", "Bucket summary", True, 30, "medium", "Combined household bucket totals."),
        ("per_person_contributions", "Individual contributions", True, 40, "wide", "How each person contributes to the buckets this cycle."),
        ("due_before_next_payday", "Due before next payday", True, 50, "wide", "Upcoming bills due before the next payday."),
        ("overdue_bills", "Overdue bills", True, 60, "wide", "Unpaid bills with due dates before today."),
        ("planned_purchases", "Planned purchases", False, 70, "medium", "Active planned purchases and quick-add saved amount."),
        ("account_balance", "Bills account balance", False, 80, "medium", "Latest manual bills account balance snapshot."),
        ("due_next_30_days", "Due in next 30 days", False, 90, "wide", "All unpaid bills due in the next 30 days."),
        ("recurring_totals", "Recurring totals", False, 100, "medium", "Monthly average and annual recurring bill totals."),
    ]
    existing = {widget.widget_key: widget for widget in DashboardWidget.query.all()}
    for key, title, enabled, sort_order, size, description in defaults:
        if key not in existing:
            db.session.add(DashboardWidget(
                widget_key=key,
                title=title,
                enabled=enabled,
                sort_order=sort_order,
                size=size,
                description=description,
            ))


def seed_default_data():
    """Create the first admin, default settings, and starter categories."""
    if not User.query.first():
        username = os.environ.get("SOLACE_ADMIN_USERNAME", "admin")
        password = os.environ.get("SOLACE_ADMIN_PASSWORD", "admin")
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role="admin",
            active=True,
        )
        db.session.add(user)

    if not Settings.query.first():
        settings = Settings(
            household_name="Project Solace",
            budget_year=2026,
            first_payday="2026-01-09",
            pay_frequency="fortnightly",
            default_buffer_amount=0,
            currency_symbol="$",
            theme="Light",
            setup_checklist_dismissed=False,
        )
        db.session.add(settings)

    if not Category.query.first():
        starter_categories = [
            ("Utilities", "Bill"),
            ("Insurance", "Bill"),
            ("Subscriptions", "Bill"),
            ("Vehicle", "Both"),
            ("House", "Both"),
            ("Pets", "Both"),
            ("Medical", "Both"),
            ("Christmas", "Purchase"),
            ("Travel", "Purchase"),
            ("Other", "Both"),
        ]
        for name, category_type in starter_categories:
            db.session.add(Category(name=name, category_type=category_type, active=True))


    if not Bucket.query.first():
        starter_buckets = [
            ("Bills", 25, 10, "Bills", 10),
            ("Savings", 20, 10, "Savings", 20),
            ("Shared spending", 45, 10, "Spending", 30),
            ("Individual spending", 10, 10, "Other", 40),
        ]
        for name, percentage, rounding_increment, bucket_type, sort_order in starter_buckets:
            db.session.add(Bucket(
                name=name,
                percentage=percentage,
                rounding_increment=rounding_increment,
                bucket_type=bucket_type,
                sort_order=sort_order,
                active=True,
            ))

    db.session.commit()

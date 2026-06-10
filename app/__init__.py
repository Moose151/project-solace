import os
import warnings
from contextlib import contextmanager
from datetime import date

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash
from sqlalchemy import text

from .models import db, User, Settings, Category, Bucket, IncomeSource, SharedIncomeAllocation, DashboardWidget, NotificationSetting, PlannedPurchase
from .version import APP_VERSION, APP_RELEASE_NAME

login_manager = LoginManager()
login_manager.login_view = "main.login"
csrf = CSRFProtect()


@contextmanager
def startup_database_lock(app):
    """Serialise startup database setup across Gunicorn workers.

    This prevents two workers from trying to create/seed the SQLite database at
    the same time during container startup. The lock file lives in the persistent
    instance folder, so it also works with the Docker volume.
    """
    os.makedirs(app.instance_path, exist_ok=True)
    lock_path = os.path.join(app.instance_path, ".startup.lock")

    with open(lock_path, "w") as lock_file:
        try:
            import fcntl
        except ImportError:
            # Windows development fallback. The production Docker path is Linux
            # and still uses a real file lock.
            yield
            return

        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def create_app():
    """Create and configure the Project Solace Flask app."""
    app = Flask(__name__, instance_relative_config=True)

    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        warnings.warn(
            "FLASK_SECRET_KEY is not set. Using an insecure development fallback.",
            RuntimeWarning,
            stacklevel=2,
        )
        secret_key = "dev-change-me"
    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(app.instance_path, "solace.db"),
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {
            "timeout": 30,
            "check_same_thread": False,
        },
        "pool_pre_ping": True,
    }
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
    app.config["APP_VERSION"] = APP_VERSION
    app.config["APP_RELEASE_NAME"] = APP_RELEASE_NAME

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        with startup_database_lock(app):
            configure_sqlite()
            db.create_all()
            apply_lightweight_migrations()
            seed_default_data()
            seed_dashboard_widgets()
            seed_notification_settings()

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def configure_sqlite():
    """Enable safer SQLite behaviour for a small multi-user household app."""
    uri = db.engine.url.drivername
    if not uri.startswith("sqlite"):
        return

    with db.engine.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
        connection.execute(text("PRAGMA synchronous=NORMAL"))
        connection.execute(text("PRAGMA busy_timeout=30000"))


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

    if not column_exists("settings", "show_help_tips"):
        db.session.execute(text("ALTER TABLE settings ADD COLUMN show_help_tips BOOLEAN NOT NULL DEFAULT 1"))

    if not column_exists("settings", "payday_bill_handling"):
        db.session.execute(text("ALTER TABLE settings ADD COLUMN payday_bill_handling VARCHAR(20) NOT NULL DEFAULT 'new_cycle'"))

    if not column_exists("bucket", "cap_to_remaining"):
        db.session.execute(text("ALTER TABLE bucket ADD COLUMN cap_to_remaining BOOLEAN NOT NULL DEFAULT 0"))

    if not column_exists("income_source", "owner_name"):
        db.session.execute(text("ALTER TABLE income_source ADD COLUMN owner_name VARCHAR(120) NOT NULL DEFAULT 'Household'"))

    if not column_exists("income_source", "income_scope"):
        db.session.execute(text("ALTER TABLE income_source ADD COLUMN income_scope VARCHAR(20) NOT NULL DEFAULT 'Individual'"))

    if not column_exists("income_source", "allocation_mode"):
        db.session.execute(text("ALTER TABLE income_source ADD COLUMN allocation_mode VARCHAR(20) NOT NULL DEFAULT 'standard'"))

    if not column_exists("income_source", "lump_bucket_id"):
        db.session.execute(text("ALTER TABLE income_source ADD COLUMN lump_bucket_id INTEGER REFERENCES bucket(id)"))

    if not column_exists("planned_purchase", "purchase_scope"):
        db.session.execute(text("ALTER TABLE planned_purchase ADD COLUMN purchase_scope VARCHAR(20) NOT NULL DEFAULT 'Shared'"))

    if not column_exists("planned_purchase", "owner_name"):
        db.session.execute(text("ALTER TABLE planned_purchase ADD COLUMN owner_name VARCHAR(120)"))

    for purchase in PlannedPurchase.query.filter((PlannedPurchase.purchase_scope == None) | (PlannedPurchase.purchase_scope == "")).all():
        purchase.purchase_scope = "Shared"

    # Indexes added during beta hardening. CREATE INDEX IF NOT EXISTS keeps
    # existing SQLite installs upgrade-safe without Alembic.
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_bill_occurrence_due_date ON bill_occurrence (due_date)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_bill_occurrence_status ON bill_occurrence (status)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_bill_occurrence_recurring_bill_id ON bill_occurrence (recurring_bill_id)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_payday_checklist_item_cycle_start ON payday_checklist_item (cycle_start)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log (created_at)"))

    capped_buckets = Bucket.query.filter(Bucket.cap_to_remaining.is_(True)).order_by(Bucket.sort_order, Bucket.name).all()
    for bucket in capped_buckets[1:]:
        bucket.cap_to_remaining = False

    db.session.commit()



def seed_dashboard_widgets():
    """Create default dashboard widgets for modular dashboard layout."""
    defaults = [
        ("setup_checklist", "Setup checklist", True, 5, "wide", "Initial setup prompts. Can be hidden once the app is configured."),
        ("quick_links", "Quick links", True, 8, "small", "Shortcut buttons for Bills, Add Bill, Calendar, and Category Overview."),
        ("set_aside_summary", "Set-aside summary", True, 10, "wide", "Main fortnightly set-aside number and components."),
        ("income_summary", "Income summary", True, 20, "medium", "Expected household income and remaining amount after bucket transfers."),
        ("bucket_summary", "Bucket summary", True, 30, "medium", "Combined household bucket totals."),
        ("per_person_contributions", "Individual contributions", True, 40, "wide", "How each person contributes to the buckets this cycle."),
        ("bills_bucket_health", "Bills bucket health", True, 45, "medium", "Shows whether the bills bucket covers the fortnightly bills requirement."),
        ("payday_checklist", "Payday checklist", True, 48, "medium", "Quick link to the transfer checklist for payday."),
        ("due_before_next_payday", "Due this cycle", True, 50, "wide", "Upcoming bills due before the current cycle ends."),
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
    db.session.commit()


def seed_notification_settings():
    """Create the single notification settings row."""
    if not NotificationSetting.query.first():
        db.session.add(NotificationSetting(
            enabled=False,
            dashboard_reminders=True,
            due_soon_days=3,
            provider="None",
        ))
        db.session.commit()

def seed_default_data():
    """Create default records without duplicating data on restart.

    This function is intentionally idempotent. It checks for existing records
    before creating them so Docker/Gunicorn restarts do not create duplicate
    rows or hit the default admin UNIQUE constraint.
    """
    username = os.environ.get("SOLACE_ADMIN_USERNAME", "admin")
    password = os.environ.get("SOLACE_ADMIN_PASSWORD")
    if not password:
        warnings.warn(
            "SOLACE_ADMIN_PASSWORD is not set. Using an insecure development fallback.",
            RuntimeWarning,
            stacklevel=2,
        )
        password = "admin"

    if not User.query.filter_by(username=username).first():
        db.session.add(User(
            username=username,
            password_hash=generate_password_hash(password),
            role="admin",
            active=True,
        ))
        db.session.commit()

    if not Settings.query.first():
        db.session.add(Settings(
            household_name="Project Solace",
            budget_year=date.today().year,
            first_payday=date.today().isoformat(),
            pay_frequency="fortnightly",
            default_buffer_amount=0,
            currency_symbol="$",
            theme="Light",
            setup_checklist_dismissed=False,
            show_help_tips=True,
            payday_bill_handling="new_cycle",
        ))
        db.session.commit()

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
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name, category_type=category_type, active=True))
    db.session.commit()

    starter_buckets = [
        ("Bills", 25, 10, "Bills", 10),
        ("Savings", 20, 10, "Savings", 20),
        ("Shared spending", 45, 10, "Spending", 30),
        ("Individual spending", 10, 10, "Other", 40),
    ]
    for name, percentage, rounding_increment, bucket_type, sort_order in starter_buckets:
        if not Bucket.query.filter_by(name=name).first():
            db.session.add(Bucket(
                name=name,
                percentage=percentage,
                rounding_increment=rounding_increment,
                bucket_type=bucket_type,
                sort_order=sort_order,
                active=True,
            ))
    db.session.commit()


import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash
from sqlalchemy import text

from .models import db, User, Settings, Category

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
    db.session.commit()


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

    db.session.commit()

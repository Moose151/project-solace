import importlib


def test_core_pages_load_with_fresh_database(tmp_path, monkeypatch):
    db_path = tmp_path / "solace-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret")
    monkeypatch.setenv("SOLACE_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("SOLACE_ADMIN_PASSWORD", "admin")

    app_module = importlib.import_module("app")
    app = app_module.create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        response = client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        assert response.status_code == 200

        for path in ["/", "/purchases", "/system-info", "/health-check", "/payday-checklist", "/pay-split", "/calendar"]:
            response = client.get(path, follow_redirects=True)
            assert response.status_code == 200, path

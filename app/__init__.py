from pathlib import Path

from flask import Flask, render_template
from sqlalchemy import inspect, text

from .assets import asset_css_urls, asset_url
from .config import Config
from .extensions import csrf, db


def _migrate_schema():
    db.create_all()
    inspector = inspect(db.engine)
    if inspector.has_table("site"):
        existing = {col["name"] for col in inspector.get_columns("site")}
        migrated = False
        if "notes" not in existing:
            db.session.execute(text("ALTER TABLE site ADD COLUMN notes TEXT"))
            migrated = True
        if "asset_paths" not in existing:
            db.session.execute(text("ALTER TABLE site ADD COLUMN asset_paths TEXT"))
            migrated = True
        if "db_path" not in existing:
            db.session.execute(text("ALTER TABLE site ADD COLUMN db_path VARCHAR(600)"))
            migrated = True
        if "db_only" not in existing:
            db.session.execute(text("ALTER TABLE site ADD COLUMN db_only BOOLEAN NOT NULL DEFAULT 0"))
            migrated = True
        if "backup_script_path" not in existing:
            db.session.execute(text("ALTER TABLE site ADD COLUMN backup_script_path VARCHAR(600)"))
            migrated = True
        if "backup_interval_days" not in existing:
            db.session.execute(text("ALTER TABLE site ADD COLUMN backup_interval_days INTEGER NOT NULL DEFAULT 7"))
            migrated = True
        if "last_backup_at" not in existing:
            db.session.execute(text("ALTER TABLE site ADD COLUMN last_backup_at DATETIME"))
            migrated = True
        if migrated:
            db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    Path(app.config["SITE_IMAGES_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    from .api.routes import api_bp
    from .main.routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    with app.app_context():
        _migrate_schema()

    app.jinja_env.globals["asset_url"] = asset_url
    app.jinja_env.globals["asset_css_urls"] = asset_css_urls

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("403.html"), 403

    @app.cli.command("init-db")
    def init_db():
        with app.app_context():
            _migrate_schema()
            print("Database initialized.")

    return app

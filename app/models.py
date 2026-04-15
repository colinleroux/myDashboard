from datetime import datetime, timezone

from .extensions import db


class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(300), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=True)
    scheme = db.Column(db.String(10), nullable=False, default="http")
    image_url = db.Column(db.String(600), nullable=True)
    github_url = db.Column(db.String(600), nullable=True)
    assets_path = db.Column(db.String(600), nullable=True)
    asset_paths = db.Column(db.Text, nullable=True)
    backup_script_path = db.Column(db.String(600), nullable=True)
    backup_interval_days = db.Column(db.Integer, nullable=False, default=7)
    last_backup_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    def destination_url(self) -> str:
        host = (self.host or "").strip()
        if host.startswith("http://") or host.startswith("https://"):
            return host

        scheme = (self.scheme or "http").strip()
        if self.port:
            return f"{scheme}://{host}:{self.port}"
        return f"{scheme}://{host}"

    def get_asset_paths(self) -> list[str]:
        values: list[str] = []

        if self.asset_paths:
            values.extend(self.asset_paths.splitlines())

        if self.assets_path:
            values.append(self.assets_path)

        cleaned: list[str] = []
        for value in values:
            candidate = (value or "").strip()
            if candidate and candidate not in cleaned:
                cleaned.append(candidate)
        return cleaned

    def is_backup_fresh(self) -> bool:
        if self.last_backup_at is None:
            return False
        interval_days = self.backup_interval_days or 7
        now = datetime.now(timezone.utc)
        last_backup = self.last_backup_at
        if last_backup.tzinfo is None:
            last_backup = last_backup.replace(tzinfo=timezone.utc)
        age = now - last_backup
        return age.days <= max(1, interval_days)


class AppSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

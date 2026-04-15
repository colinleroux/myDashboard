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
    db_path = db.Column(db.String(600), nullable=True)
    db_only = db.Column(db.Boolean, default=False, nullable=False)
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

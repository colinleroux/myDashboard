import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DB = BASE_DIR / "instance" / "app.db"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        f"sqlite:///{INSTANCE_DB.as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BACKUP_ROOT = os.environ.get(
        "BACKUP_ROOT",
        str((BASE_DIR / "instance" / "backups").resolve()),
    )
    SITE_IMAGES_DIR = os.environ.get(
        "SITE_IMAGES_DIR",
        str((BASE_DIR / "instance" / "site_images").resolve()),
    )

from datetime import datetime
from pathlib import Path
import shutil
from typing import Optional
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Site

main_bp = Blueprint("main", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}


def _normalize_port(raw_port: str):
    cleaned = (raw_port or "").strip()
    if cleaned == "":
        return None
    try:
        port = int(cleaned)
    except ValueError:
        return None
    if port < 1 or port > 65535:
        return None
    return port


def _sqlite_db_file() -> Optional[Path]:
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not db_uri.startswith("sqlite:///"):
        return None
    return Path(db_uri.replace("sqlite:///", "", 1)).resolve()


def _ensure_backup_dir(prefix: str) -> Path:
    backup_root = Path(current_app.config["BACKUP_ROOT"]).resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = backup_root / f"{stamp}-{prefix}"
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def _copy_site_assets(site: Site, destination: Path):
    for path_value in site.get_asset_paths():
        source = Path(path_value).expanduser().resolve()
        if not source.exists():
            flash(f"Assets path for '{site.name}' does not exist: {source}", "warning")
            continue

        if source.is_file():
            shutil.copy2(source, destination / source.name)
            continue

        shutil.copytree(source, destination / source.name, dirs_exist_ok=True)


def _copy_database(destination: Path):
    db_path = _sqlite_db_file()
    if db_path is None:
        flash("Database backup supports SQLite URIs only in this version.", "warning")
        return
    if not db_path.exists():
        flash(f"Database file not found: {db_path}", "warning")
        return
    shutil.copy2(db_path, destination / db_path.name)


def _copy_site_database(site: Site, destination: Path):
    if not site.db_path:
        return

    db_path = Path(site.db_path).expanduser().resolve()
    if not db_path.exists():
        flash(f"Database path for '{site.name}' does not exist: {db_path}", "warning")
        return

    if db_path.is_dir():
        flash(f"Database path for '{site.name}' must be a file: {db_path}", "warning")
        return

    shutil.copy2(db_path, destination / db_path.name)


def _copy_managed_images(destination: Path):
    source = Path(current_app.config["SITE_IMAGES_DIR"]).resolve()
    if source.exists():
        shutil.copytree(source, destination / source.name, dirs_exist_ok=True)


def _image_extension(filename: str) -> Optional[str]:
    if "." not in filename:
        return None
    extension = filename.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    return extension


def _save_uploaded_image():
    file = request.files.get("image_file")
    if file is None or not file.filename:
        return None

    extension = _image_extension(file.filename)
    if extension is None:
        flash("Unsupported image file type.", "error")
        return None

    image_dir = Path(current_app.config["SITE_IMAGES_DIR"]).resolve()
    image_dir.mkdir(parents=True, exist_ok=True)
    base_name = secure_filename(file.filename.rsplit(".", 1)[0]) or "site-image"
    filename = f"{base_name}-{uuid4().hex[:10]}.{extension}"
    destination = image_dir / filename
    file.save(destination)
    return url_for("main.site_image", filename=filename)


def _form_asset_paths() -> list[str]:
    values = request.form.getlist("asset_paths")
    cleaned: list[str] = []
    for value in values:
        candidate = (value or "").strip()
        if candidate and candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


@main_bp.route("/")
def home():
    sites = Site.query.order_by(Site.name.asc()).all()
    return render_template("home.html", sites=sites)


@main_bp.route("/site-images/<path:filename>")
def site_image(filename: str):
    image_dir = Path(current_app.config["SITE_IMAGES_DIR"]).resolve()
    return send_from_directory(image_dir, filename)


@main_bp.route("/settings")
def settings():
    sites = Site.query.order_by(Site.name.asc()).all()
    return render_template("settings.html", sites=sites)


@main_bp.route("/sites/create", methods=["POST"])
def create_site():
    name = request.form.get("name", "").strip()
    host = request.form.get("host", "").strip()
    description = request.form.get("description", "").strip()
    notes = request.form.get("notes", "").strip()
    scheme = request.form.get("scheme", "http").strip().lower()
    image_url = request.form.get("image_url", "").strip()
    github_url = request.form.get("github_url", "").strip()
    db_path = request.form.get("db_path", "").strip()
    db_only = request.form.get("db_only") == "on"
    asset_paths = _form_asset_paths()
    port = _normalize_port(request.form.get("port", ""))

    if not name or not host:
        flash("Name and address are required.", "error")
        return redirect(url_for("main.settings"))

    if scheme not in {"http", "https"}:
        flash("Scheme must be http or https.", "error")
        return redirect(url_for("main.settings"))

    if request.form.get("port", "").strip() and port is None:
        flash("Port must be between 1 and 65535.", "error")
        return redirect(url_for("main.settings"))

    uploaded_image_url = _save_uploaded_image()
    if request.files.get("image_file") and uploaded_image_url is None:
        return redirect(url_for("main.settings"))

    site = Site(
        name=name,
        host=host,
        port=port,
        scheme=scheme,
        description=description or None,
        notes=notes or None,
        image_url=uploaded_image_url or image_url or None,
        github_url=github_url or None,
        assets_path=asset_paths[0] if asset_paths else None,
        asset_paths="\n".join(asset_paths) if asset_paths else None,
        db_path=db_path or None,
        db_only=db_only,
    )
    db.session.add(site)
    db.session.commit()

    flash(f"Added site '{site.name}'.", "success")
    return redirect(url_for("main.settings"))


@main_bp.route("/sites/<int:site_id>/update", methods=["POST"])
def update_site(site_id: int):
    site = db.session.get(Site, site_id)
    if site is None:
        flash("Site not found.", "error")
        return redirect(url_for("main.settings"))

    name = request.form.get("name", "").strip()
    host = request.form.get("host", "").strip()
    description = request.form.get("description", "").strip()
    notes = request.form.get("notes", "").strip()
    scheme = request.form.get("scheme", "http").strip().lower()
    image_url = request.form.get("image_url", "").strip()
    github_url = request.form.get("github_url", "").strip()
    db_path = request.form.get("db_path", "").strip()
    db_only = request.form.get("db_only") == "on"
    asset_paths = _form_asset_paths()
    raw_port = request.form.get("port", "")
    port = _normalize_port(raw_port)

    if not name or not host:
        flash("Name and address are required.", "error")
        return redirect(url_for("main.settings"))

    if scheme not in {"http", "https"}:
        flash("Scheme must be http or https.", "error")
        return redirect(url_for("main.settings"))

    if raw_port.strip() and port is None:
        flash("Port must be between 1 and 65535.", "error")
        return redirect(url_for("main.settings"))

    uploaded_image_url = _save_uploaded_image()
    if request.files.get("image_file") and uploaded_image_url is None:
        return redirect(url_for("main.settings"))

    site.name = name
    site.host = host
    site.port = port
    site.scheme = scheme
    site.description = description or None
    site.notes = notes or None
    site.image_url = uploaded_image_url or image_url or None
    site.github_url = github_url or None
    site.assets_path = asset_paths[0] if asset_paths else None
    site.asset_paths = "\n".join(asset_paths) if asset_paths else None
    site.db_path = db_path or None
    site.db_only = db_only
    db.session.commit()

    flash(f"Updated site '{site.name}'.", "success")
    return redirect(url_for("main.settings"))


@main_bp.route("/sites/<int:site_id>/delete", methods=["POST"])
def delete_site(site_id: int):
    site = db.session.get(Site, site_id)
    if site is None:
        flash("Site not found.", "error")
        return redirect(url_for("main.settings"))

    db.session.delete(site)
    db.session.commit()

    flash("Site deleted.", "info")
    return redirect(url_for("main.settings"))


@main_bp.route("/sites/<int:site_id>/backup", methods=["POST"])
def backup_site(site_id: int):
    site = db.session.get(Site, site_id)
    if site is None:
        flash("Site not found.", "error")
        return redirect(url_for("main.home"))

    destination = _ensure_backup_dir(f"site-{site_id}")
    _copy_database(destination)
    _copy_managed_images(destination)
    _copy_site_database(site, destination)
    if not site.db_only:
        _copy_site_assets(site, destination)

    flash(f"Backup finished for '{site.name}' at {destination}.", "success")
    return redirect(url_for("main.home"))


@main_bp.route("/backup-all", methods=["POST"])
def backup_all():
    sites = Site.query.order_by(Site.id.asc()).all()
    destination = _ensure_backup_dir("all-sites")
    _copy_database(destination)
    _copy_managed_images(destination)
    for site in sites:
        site_dir = destination / f"site-{site.id}-{site.name.replace(' ', '-').lower()}"
        site_dir.mkdir(parents=True, exist_ok=True)
        _copy_site_database(site, site_dir)
        if not site.db_only:
            _copy_site_assets(site, site_dir)

    flash(f"Backup all finished at {destination}.", "success")
    return redirect(url_for("main.home"))


@main_bp.route("/scripts")
def scripts():
    return render_template("scripts.html")

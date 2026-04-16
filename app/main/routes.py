from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Optional
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import AppSetting, Site

main_bp = Blueprint("main", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
SETTING_BACKUP_ALL_SCRIPT_PATH = "backup_all_script_path"
SETTING_LOGS_DIR = "logs_dir"


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


def _form_backup_interval_days() -> Optional[int]:
    raw_value = (request.form.get("backup_interval_days") or "").strip()
    if not raw_value:
        return 7
    try:
        value = int(raw_value)
    except ValueError:
        return None
    if value < 1 or value > 365:
        return None
    return value


def _get_setting(key: str, default: str = "") -> str:
    setting = AppSetting.query.filter_by(key=key).first()
    if setting is None or setting.value is None:
        return default
    return setting.value


def _set_setting(key: str, value: str):
    setting = AppSetting.query.filter_by(key=key).first()
    if setting is None:
        setting = AppSetting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value


def _logs_dir_path() -> Path:
    configured = (_get_setting(SETTING_LOGS_DIR, current_app.config.get("LOGS_DIR", "")) or "").strip()
    if not configured:
        configured = (current_app.config.get("LOGS_DIR") or "").strip() or "."
    preferred = Path(configured).expanduser()
    if preferred.exists():
        return preferred

    fallbacks = [
        Path("/mnt/backup/logs"),
        Path("/mnt/data/backup/logs"),
    ]
    for fallback in fallbacks:
        if fallback.exists():
            return fallback
    return preferred


def _resolve_script_path(script_path: str) -> tuple[Optional[Path], list[Path]]:
    raw = (script_path or "").strip()
    if not raw:
        return None, []

    candidate = Path(raw).expanduser()
    tried: list[Path] = [candidate]
    if candidate.exists():
        return candidate, tried

    text_candidate = str(candidate)
    if text_candidate.startswith("/mnt/backup/backup_scripts/"):
        translated = Path(text_candidate.replace("/mnt/backup/backup_scripts/", "/mnt/data/backup_scripts/", 1))
        tried.append(translated)
        if translated.exists():
            return translated, tried

    if text_candidate.startswith("/mnt/data/backup_scripts/"):
        translated = Path(text_candidate.replace("/mnt/data/backup_scripts/", "/mnt/backup/backup_scripts/", 1))
        tried.append(translated)
        if translated.exists():
            return translated, tried

    if "/" not in raw and "\\" not in raw:
        for base in (Path("/mnt/data/backup_scripts"), Path("/mnt/backup/backup_scripts")):
            translated = base / raw
            tried.append(translated)
            if translated.exists():
                return translated, tried

    return None, tried


def _run_script(script_path: str, label: str) -> bool:
    cleaned = (script_path or "").strip()
    if not cleaned:
        flash(f"{label} script path is not configured.", "error")
        return False

    script, tried_paths = _resolve_script_path(cleaned)
    if script is None:
        tried = ", ".join(str(path) for path in tried_paths) if tried_paths else cleaned
        flash(f"{label} script not found. Tried: {tried}", "error")
        return False

    command = ["bash", str(script)] if script.suffix == ".sh" else [str(script)]
    timeout_seconds = int(current_app.config.get("SCRIPT_TIMEOUT_SECONDS", 3600))

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except Exception as exc:
        flash(f"{label} script failed to start: {exc}", "error")
        return False

    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        summary = details[-300:] if details else "No error output."
        flash(f"{label} script failed (exit {result.returncode}). {summary}", "error")
        return False

    flash(f"{label} completed successfully.", "success")
    return True


def _is_manual_backup_site(site: Site) -> bool:
    # Keep Immich manual: excluded from Backup All status updates.
    script_path = (site.backup_script_path or "").lower()
    site_name = (site.name or "").lower()
    return "immich" in site_name or "immich" in script_path


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
    backup_all_script_path = _get_setting(
        SETTING_BACKUP_ALL_SCRIPT_PATH,
        current_app.config.get("BACKUP_ALL_SCRIPT_PATH", ""),
    )
    logs_dir = _get_setting(SETTING_LOGS_DIR, current_app.config.get("LOGS_DIR", ""))
    return render_template(
        "settings.html",
        sites=sites,
        backup_all_script_path=backup_all_script_path,
        logs_dir=logs_dir,
    )


@main_bp.route("/settings/app", methods=["POST"])
def update_app_settings():
    backup_all_script_path = (request.form.get("backup_all_script_path") or "").strip()
    logs_dir = (request.form.get("logs_dir") or "").strip()

    _set_setting(SETTING_BACKUP_ALL_SCRIPT_PATH, backup_all_script_path)
    _set_setting(SETTING_LOGS_DIR, logs_dir)
    db.session.commit()

    flash("Application settings updated.", "success")
    return redirect(url_for("main.settings"))


@main_bp.route("/sites/create", methods=["POST"])
def create_site():
    name = request.form.get("name", "").strip()
    host = request.form.get("host", "").strip()
    description = request.form.get("description", "").strip()
    notes = request.form.get("notes", "").strip()
    scheme = request.form.get("scheme", "http").strip().lower()
    image_url = request.form.get("image_url", "").strip()
    github_url = request.form.get("github_url", "").strip()
    backup_script_path = request.form.get("backup_script_path", "").strip()
    backup_interval_days = _form_backup_interval_days()
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

    if backup_interval_days is None:
        flash("Backup freshness window must be between 1 and 365 days.", "error")
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
        backup_script_path=backup_script_path or None,
        backup_interval_days=backup_interval_days,
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
    backup_script_path = request.form.get("backup_script_path", "").strip()
    backup_interval_days = _form_backup_interval_days()
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

    if backup_interval_days is None:
        flash("Backup freshness window must be between 1 and 365 days.", "error")
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
    site.backup_script_path = backup_script_path or None
    site.backup_interval_days = backup_interval_days
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

    success = _run_script(site.backup_script_path or "", site.name)
    if success:
        site.last_backup_at = datetime.now(timezone.utc)
        db.session.commit()
    return redirect(url_for("main.home"))


@main_bp.route("/backup-all", methods=["POST"])
def backup_all():
    backup_all_script_path = _get_setting(
        SETTING_BACKUP_ALL_SCRIPT_PATH,
        current_app.config.get("BACKUP_ALL_SCRIPT_PATH", ""),
    )
    success = _run_script(backup_all_script_path, "Backup all")
    if success:
        now = datetime.now(timezone.utc)
        for site in Site.query.all():
            if _is_manual_backup_site(site):
                continue
            site.last_backup_at = now
        db.session.commit()
        flash("Immich is excluded from Backup all status updates and remains manual.", "info")
    return redirect(url_for("main.home"))


@main_bp.route("/logs")
def logs():
    logs_dir = _logs_dir_path()
    log_files: list[dict] = []

    if logs_dir.exists() and logs_dir.is_dir():
        for path in logs_dir.iterdir():
            if not path.is_file():
                continue
            stats = path.stat()
            log_files.append(
                {
                    "name": path.name,
                    "size": stats.st_size,
                    "modified_at": datetime.fromtimestamp(stats.st_mtime),
                }
            )
        log_files.sort(key=lambda item: item["modified_at"], reverse=True)
    else:
        flash(f"Logs directory not found: {logs_dir}", "warning")

    return render_template("logs.html", log_files=log_files, logs_dir=str(logs_dir))


@main_bp.route("/logs/<path:filename>")
def log_file(filename: str):
    logs_dir = _logs_dir_path()
    logs_dir_resolved = logs_dir.resolve()
    file_path = (logs_dir_resolved / filename).resolve()
    if logs_dir_resolved != file_path and logs_dir_resolved not in file_path.parents:
        flash("Invalid log file path.", "error")
        return redirect(url_for("main.logs"))
    if not file_path.exists() or not file_path.is_file():
        flash("Log file not found.", "error")
        return redirect(url_for("main.logs"))

    content = file_path.read_text(encoding="utf-8", errors="replace")
    return render_template("log_detail.html", filename=filename, content=content)

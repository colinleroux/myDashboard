# Internal Site Launcher (SQLite)

Internal dashboard for launching self-hosted services, running backup scripts, and checking backup/log status.

## Features

- Landing page with site tiles and quick links.
- Tile backup status colors:
  - Green when last backup is within the configured freshness window.
  - Amber when backup is missing or older than the freshness window.
- Per-site backup script path and freshness window (days).
- Global `Backup all` script path.
- Logs page that lists log files with modified time and size, with click-through file view.
- Site metadata:
  - Name, host, port, scheme
  - Description and notes
  - Image URL or uploaded image
  - GitHub URL
  - Asset/reference paths (for your own file-location notes)

## Quick Start (Docker)

```bash
docker compose build
docker compose up
```

Open: `http://localhost:8000`

## Quick Start (Local)

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
npm run build
flask --app wsgi_app.py init-db
python run.py
```

## Environment Variables

- `BACKUP_ALL_SCRIPT_PATH` (optional default for Backup all path)
- `LOGS_DIR` (default: `/mnt/backup/logs`)
- `SCRIPT_TIMEOUT_SECONDS` (default: `3600`)
- `SITE_IMAGES_DIR` (default: `instance/site_images`)

## API

- `GET /api/health`
- `GET /api/stats`

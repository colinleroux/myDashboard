# Internal Site Launcher (SQLite)

This project is a no-auth internal dashboard for launching your self-hosted services.

## Features

- Public landing page with responsive tiles (4 across on desktop)
- Settings page to add/update/delete site tiles
- Per-site details:
  - Name
  - Address/host
  - Port
  - `http`/`https` scheme
  - Short description
  - Notes
  - Image URL or uploaded image file
  - GitHub repo URL
  - Optional per-site DB file path
  - `DB only backup` option
  - Multiple asset paths for backups
- Landing tiles include an info button that opens a details modal with a quick `Edit` link.
- Backup actions:
  - `Backup` on each tile (backs up DB + that site's assets path)
  - `Backup all` button (backs up DB + all configured assets paths)
- Placeholder `/scripts` page for future script-tile execution

## Quick start (Docker)

```bash
docker compose build
docker compose up
```

Open: `http://localhost:8000`

## Quick start (local)

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
npm run build
flask --app wsgi_app.py init-db
python run.py
```

## Backups

- Default backup output directory: `instance/backups`
- Override with environment variable: `BACKUP_ROOT`
- Each backup run creates a timestamped folder.

Notes:
- This version supports SQLite database backup.
- Assets are copied from each site's optional `assets_path` if provided.
- Uploaded images are stored in `instance/site_images` (override with `SITE_IMAGES_DIR`).

## API

- `GET /api/health`
- `GET /api/stats` (returns configured site count)

For your copyfiles.py example, the tile flow should be:

Tile click sends POST /scripts/run/<script_id> in launcher.
Launcher creates a job record (queued) in DB.
Launcher executes script in a controlled way, for example:
python /mounted/scripts/copyfiles.py --src ... --dst ...
Capture:
exit code
stdout/stderr
start/end timestamps
Update job record to success or failed.
UI tile shows latest status badge and “last run” details.
What to show in tile/UI:

Running... / Success / Failed
last run time
short message (first line of stdout/stderr)
optional “View logs” modal for full output
Recommended safety rules:

Only allow scripts from a whitelisted mounted folder.
Store script metadata in DB (name, path, args template, timeout).
Run with timeout and max output size.
No arbitrary shell from user input.
So yes: tile can trigger script, and we can show live/result status directly on the tile plus full logs in a modal.


how does this occur? Launcher executes script in a controlled way, for example:
python /mounted/scripts/copyfiles.py --src ... --dst ...



It happens in the backend route, not in the browser.

When you click a tile button, the UI sends a POST to the launcher API. That handler runs a subprocess command on the machine where the launcher process is running (in your case, likely the launcher container).

Example backend pattern:

import subprocess

cmd = [
    "python",
    "/mounted/scripts/copyfiles.py",
    "--src", "/mounted/data/a",
    "--dst", "/mounted/data/b",
]

result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=600,
)
Then we store:

result.returncode (0 = success, non-zero = failed)
result.stdout
result.stderr
start/end timestamps
And return that status to UI so the tile can show Success or Failed.

Important in Docker:

/mounted/scripts/... and source/destination paths must be bind-mounted into launcher container.
If paths are host-only and not mounted, this won’t work from inside container.
In that case, use a host-runner service (launcher queues job, host executes it).
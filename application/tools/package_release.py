"""Create a source-only handover archive from explicitly allowed project paths, excluding local credentials."""
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def main():
    """Package allowlisted source/config/docs and report a SHA-256; never include env secrets, databases or traces."""
    root = Path(__file__).resolve().parents[1]
    top_files = ["README.md", ".env.example", ".gitignore", "compose.yaml", "start-local.ps1", "stop-local.ps1"]
    directories = ["backend/app", "backend/migrations", "backend/tests", "frontend/src", "frontend/tests", "data", "docs", "tools", ".github"]
    extra = ["backend/pyproject.toml", "backend/uv.lock", "backend/alembic.ini", "backend/Dockerfile", "backend/.dockerignore",
             "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json", "frontend/vite.config.ts",
             "frontend/playwright.config.ts", "frontend/index.html", "frontend/Dockerfile", "frontend/.dockerignore",
             "frontend/nginx.conf", "frontend/vercel.json"]
    files = [root / name for name in top_files + extra]
    for directory in directories:
        files.extend(p for p in (root / directory).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    release_dir = root.parent / "releases" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    release_dir.mkdir(parents=True, exist_ok=False)
    archive = release_dir / "fault-forge-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        for file in sorted(set(files)):
            output.write(file, "fault-forge/" + file.relative_to(root).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    record = {"archive": archive.name, "files": len(set(files)), "bytes": archive.stat().st_size, "sha256": digest,
              "excluded": [".env", "local-access.txt", "databases", "dependencies", "caches", "browser traces"]}
    (release_dir / "fault-forge-source-manifest.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()

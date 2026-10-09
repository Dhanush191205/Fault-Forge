"""Set an explicit same-origin API gateway in Vercel config after choosing a deployed backend."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def main():
    """Validate a public HTTPS backend origin and write a concrete Vercel rewrite; reject URLs with credentials."""
    parser = argparse.ArgumentParser()
    parser.add_argument("backend_origin")
    args = parser.parse_args()
    url = urlparse(args.backend_origin)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
        raise SystemExit("Use a plain HTTPS backend origin without credentials, paths or query strings.")
    config_path = Path(__file__).resolve().parents[1] / "frontend" / "vercel.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["rewrites"] = [{"source": "/api/:path*", "destination": args.backend_origin.rstrip("/") + "/api/:path*"},
                          {"source": "/:path*", "destination": "/index.html"}]
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print("Vercel gateway configured. Add the frontend HTTPS origin to backend ALLOWED_ORIGINS.")


if __name__ == "__main__":
    main()

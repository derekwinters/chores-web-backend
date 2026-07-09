#!/usr/bin/env python3
"""Generate the OpenAPI JSON snapshot for the chores-web API.

Usage:
    python scripts/generate_openapi.py [--output openapi.json]

The golden snapshot is committed in the chores-web-docs repo at
docs/api/openapi.json (contract-first). CI runs this script and uses
oasdiff to detect breaking changes against that published contract.

Breaking Change Ritual (also documented in CLAUDE.md):
1. PR to chores-web-docs: increment API_VERSION and update the golden
   docs/api/openapi.json there.
2. Mount new routes under /api/v{N}/ alongside old ones in this repo.
"""
import argparse
import json
import os
import sys

# Add the backend directory to sys.path so we can import the app
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(SCRIPT_DIR, "..")
sys.path.insert(0, BACKEND_DIR)

# Set a dummy JWT_SECRET so Settings() doesn't fail (no .env in CI)
os.environ.setdefault("JWT_SECRET", "openapi-snapshot-generation-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./snapshot.db")

from app.main import app  # noqa: E402 — must come after sys.path manipulation


def generate(output_path: str) -> None:
    schema = app.openapi()
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")
    print(f"OpenAPI snapshot written to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate OpenAPI snapshot")
    parser.add_argument(
        "--output",
        default=os.path.join(SCRIPT_DIR, "..", "openapi.json"),
        help="Output path for the OpenAPI JSON snapshot",
    )
    args = parser.parse_args()
    generate(args.output)

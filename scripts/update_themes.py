#!/usr/bin/env python3
"""Refresh the vendored built-in theme palettes from @derekwinters/design-tokens.

The six built-in palettes served by /theme are design data owned by the
chores-web-design-tokens repo. This script downloads a pinned release of the
npm package from GitHub Packages, extracts its dist/themes.json, and rewrites
app/data/themes.json (stamping the pinned version in the "_source" key).

Usage:
    python scripts/update_themes.py 0.1.0

Requires `npm` and auth for GitHub Packages, e.g. a ~/.npmrc containing:
    //npm.pkg.github.com/:_authToken=<token with read:packages>
    @chores:registry=https://npm.pkg.github.com
"""
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PACKAGE = "@derekwinters/design-tokens"
TARGET = Path(__file__).resolve().parent.parent / "app" / "data" / "themes.json"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    version = sys.argv[1]

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["npm", "pack", f"{PACKAGE}@{version}", "--pack-destination", tmp],
            check=True,
        )
        tarball = next(Path(tmp).glob("*.tgz"))
        with tarfile.open(tarball) as tf:
            member = tf.getmember("package/dist/themes.json")
            themes = json.loads(tf.extractfile(member).read())

    out = {"_source": f"{PACKAGE}@{version}"}
    out.update(themes)
    TARGET.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {TARGET} from {PACKAGE}@{version} ({len(themes)} themes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

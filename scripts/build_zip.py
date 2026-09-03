#!/usr/bin/env python3
"""Zip plugin.json + backend (+ skills/assets) for Store upload. No secrets."""

from __future__ import annotations

import json
import zipfile
import pathlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "deploy"


def _prune_superseded_zips(keep: pathlib.Path | None = None) -> None:
    """Delete every built zip except the one just built.

    deploy/ is gitignored build output; superseded zips are stale files that
    pile up one per version bump and can be re-created by re-running this
    script. Keeping them only invites installing an old build by mistake.
    """
    try:
        zips = sorted(OUT_DIR.glob("*.ducky-plugin.zip"))
    except OSError:
        return
    survivor = keep
    if survivor is None and zips:
        survivor = max(zips, key=lambda p: p.stat().st_mtime)
    for z in zips:
        try:
            if survivor is not None and z.samefile(survivor):
                continue
            z.unlink()
        except OSError:
            pass
SKIP_NAMES = {".git", "scripts", "deploy", ".gitignore", "README.md", "__pycache__"}
SKIP_SUFFIX = {".pyc", ".pyo", ".zip", ".ducky-plugin"}


def build_zip(*, out: Path | None = None) -> Path:
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    pid = str(manifest.get("id") or "").strip()
    version = manifest.get("version") or 1
    if not pid:
        raise SystemExit("plugin.json missing id")
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".dat", ".env", ".pem", ".key"}:
            raise SystemExit(f"refusing to pack secret-looking file: {path}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = out or (OUT_DIR / f"{pid}-{version}.ducky-plugin.zip")
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(ROOT).parts
            if not rel_parts or rel_parts[0] in SKIP_NAMES:
                continue
            if path.suffix.lower() in SKIP_SUFFIX or path.name.startswith("."):
                continue
            zf.write(path, arcname="/".join(rel_parts))
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")
    return dest


if __name__ == "__main__":
    _prune_superseded_zips(build_zip())

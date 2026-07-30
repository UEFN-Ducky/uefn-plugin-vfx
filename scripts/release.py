#!/usr/bin/env python3
"""Zip + publish this UEFN desktop plugin to the UEFN Ducky Store.

Uses remote MCP tools on the site plugin ``uefn-ducky-store``:
  uds_ensure_category, uds_release (create/upload + publish).

Env:
  DUCKYOS_BASE_URL   default https://uefnducky.org
  DUCKYOS_API_KEY    staff API key with mcp_remote + store manage
  UDS_CATEGORY       default plugins

Usage:
  py scripts/release.py              # zip only
  py scripts/release.py --publish    # zip + MCP upload + publish
  py scripts/release.py --publish --changelog "v1: Materials tools + skill"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from build_zip import build_zip  # noqa: E402


def _load_dotenv() -> None:
    for candidate in (ROOT / ".env", ROOT.parents[1] / ".env", ROOT.parents[1] / "DuckyOS" / ".env"):
        # parents[1] = UEFN-Ducky; also try sibling DuckyOS
        pass
    # Common: UEFN-Ducky/.env or DuckyOS/.env next to monorepo sibling
    candidates = [
        ROOT / ".env",
        ROOT.parents[1] / ".env",
        ROOT.parents[1].parent / "DuckyOS" / ".env",
        Path.home() / ".duckyos" / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def mcp_call(base_url: str, api_key: str, name: str, arguments: dict) -> dict:
    url = base_url.rstrip("/") + "/api/v1/mcp"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "UEFN-Ducky-PluginRelease/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"MCP HTTP {exc.code}: {detail}") from exc
    if payload.get("error"):
        raise SystemExit(f"MCP error: {payload['error']}")
    result = payload.get("result") or {}
    # Prefer structuredContent; fall back to text JSON.
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text = str(block.get("text") or "").strip()
            if text.startswith("{"):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return {"ok": True, "text": text}
    return result if isinstance(result, dict) else {"ok": True, "result": result}



def upload_zip_file(base_url: str, api_key: str, zip_path: Path) -> dict:
    """Multipart upload via API-key app-release route (MCP JSON bodies capped at 64KB)."""
    boundary = "----DuckyPluginZipBoundary7MA4YWxkTrZu0gW"
    file_bytes = zip_path.read_bytes()
    filename = zip_path.name
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                "Content-Type: application/zip\r\n\r\n"
            ).encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    url = base_url.rstrip("/") + "/api/files/app-release"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "UEFN-Ducky-PluginRelease/1.0",
            "Origin": base_url.rstrip("/"),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Upload HTTP {exc.code}: {detail}") from exc
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise SystemExit(f"Upload failed: {payload}")
    return payload


def publish(zip_path: Path, *, category: str, changelog: str) -> None:
    _load_dotenv()
    base = os.environ.get("DUCKYOS_BASE_URL") or os.environ.get("DUCKYOS_MARKETPLACE_URL") or "https://uefnducky.org"
    key = os.environ.get("DUCKYOS_API_KEY") or os.environ.get("DUCKYOS_MARKETPLACE_API_KEY") or ""
    if not key:
        raise SystemExit("Set DUCKYOS_API_KEY (staff key with mcp_remote scopes) to publish")
    print(f"ensuring category {category!r}…")
    mcp_call(base, key, "uds_ensure_category", {"name": category, "slug": category})
    # ponytail: MCP wire max body 64KB — upload zip then pass zipFileId (not zipB64).
    print(f"uploading {zip_path.name} via /api/files/app-release…")
    uploaded = upload_zip_file(base, key, zip_path)
    file_meta = uploaded.get("file") if isinstance(uploaded.get("file"), dict) else {}
    file_id = str(file_meta.get("id") or uploaded.get("id") or "").strip()
    zip_url = str(uploaded.get("url") or "").strip()
    if not file_id and not zip_url:
        raise SystemExit(f"Upload missing file id/url: {uploaded}")
    release_args: dict = {
        "category": category,
        "changelog": changelog,
        "publish": True,
    }
    if file_id:
        release_args["zipFileId"] = file_id
    else:
        release_args["zipUrl"] = zip_url
    print(f"releasing via uds_release ({'zipFileId=' + file_id if file_id else 'zipUrl'})…")
    result = mcp_call(base, key, "uds_release", release_args)
    print(json.dumps(result, indent=2))
    if result.get("ok") is False or result.get("error"):
        raise SystemExit(result.get("error") or "release failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Upload + publish via Store MCP")
    parser.add_argument("--sync-seed", action="store_true", help="Sync into frontend/uefn_plugins/discord")
    parser.add_argument("--changelog", default="", help="Version changelog for Store")
    parser.add_argument("--category", default=os.environ.get("UDS_CATEGORY") or "plugins")
    args = parser.parse_args()

    if args.sync_seed:
        from sync_seed import main as sync_main

        sync_main()

    zip_path = build_zip()
    if args.publish:
        publish(zip_path, category=args.category, changelog=args.changelog)
    else:
        print("zip only — pass --publish to upload/approve on the Store")


if __name__ == "__main__":
    main()

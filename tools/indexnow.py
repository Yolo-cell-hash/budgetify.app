#!/usr/bin/env python3
"""Tell Bing and friends that pages changed, instead of waiting to be crawled.

A brand-new domain can sit uncrawled for weeks. IndexNow is a push protocol:
you submit URLs and participating engines fetch them promptly. It is supported
by **Bing, Yandex, Seznam and Naver** — notably *not* by Google, which has no
equivalent and has to be reached through Search Console instead.

Bing is the reason this is worth doing for AI visibility specifically:
ChatGPT's browsing and Microsoft Copilot both lean on Bing's index, so getting
crawled by Bing is a direct input to whether an assistant can cite these pages.

## How the key works

Ownership is proved by hosting a file at the site root whose name is the key
and whose contents are the key. That file must be deployed and publicly
reachable *before* submitting, or every URL is rejected as unverified — which
is why this script checks the key file first and refuses to submit if it is
missing.

    python3 tools/indexnow.py            # submit every URL in sitemap.xml
    python3 tools/indexnow.py --check    # verify the key file only
    python3 tools/indexnow.py --url https://budgetify.dev/faq/

Re-submitting unchanged pages is pointless and, done often enough, is treated
as spam. Run it when content actually changes.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = "budgetify.dev"
SITE = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"

REPO = Path(__file__).resolve().parent.parent


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CTX = _ssl_context()


def find_key() -> str:
    """The key is whatever <key>.txt sits in the repo root."""
    keys = [p for p in REPO.glob("*.txt")
            if re.fullmatch(r"[0-9a-f]{8,128}", p.stem)]
    if not keys:
        sys.exit("No IndexNow key file found in the repo root "
                 "(expected a file named <hexkey>.txt).")
    if len(keys) > 1:
        sys.exit(f"Multiple key files found: {[k.name for k in keys]}. "
                 "Keep exactly one.")
    key = keys[0].stem
    contents = keys[0].read_text(encoding="utf-8").strip()
    if contents != key:
        sys.exit(f"{keys[0].name} must contain exactly its own key; "
                 f"found {contents!r}.")
    return key


def check_live(key: str) -> bool:
    """The key file must be reachable on the deployed site, not just locally."""
    url = f"{SITE}/{key}.txt"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "indexnow-check"})
        with urllib.request.urlopen(req, timeout=15, context=SSL_CTX) as r:
            body = r.read().decode().strip()
        if body == key:
            print(f"ok   key file live at {url}")
            return True
        print(f"FAIL {url} served {body!r}, expected the key")
    except Exception as e:
        print(f"FAIL {url} unreachable: {e}")
    return False


def sitemap_urls() -> list[str]:
    xml = (REPO / "sitemap.xml").read_text(encoding="utf-8")
    return re.findall(r"<loc>(.*?)</loc>", xml)


def submit(key: str, urls: list[str]) -> int:
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": f"{SITE}/{key}.txt",
        "urlList": urls,
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
            # 200 accepted, 202 accepted-but-key-still-validating. Both fine.
            print(f"submitted {len(urls)} URLs — HTTP {r.status}")
            return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        print(f"rejected — HTTP {e.code}: {body}")
        # 422 usually means the key file is not reachable at keyLocation.
        return 1
    except Exception as e:
        print(f"failed: {e}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the key file is live, submit nothing")
    ap.add_argument("--url", action="append", metavar="URL",
                    help="submit specific URLs instead of the whole sitemap")
    args = ap.parse_args()

    key = find_key()
    print(f"key  {key}")
    live = check_live(key)
    if args.check:
        return 0 if live else 1
    if not live:
        print("\nRefusing to submit: deploy the key file first, or every URL "
              "comes back unverified.")
        return 1

    urls = args.url or sitemap_urls()
    print("\n".join(f"  {u}" for u in urls))
    return submit(key, urls)


if __name__ == "__main__":
    sys.exit(main())

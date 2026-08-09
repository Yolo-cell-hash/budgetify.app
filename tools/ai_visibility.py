#!/usr/bin/env python3
"""Measure whether AI assistants actually name Budgetify when asked for an app.

Play rank is measurable with `aso_rank.py` in the app repo. This is the
equivalent for the other discovery surface: someone asking Claude, ChatGPT,
Gemini or Perplexity "what's a good offline expense tracker for India?".

## Why it asks the models directly

The obvious approach — scrape a search engine and see if budgetify.dev ranks —
does not work any more: Google, Bing and DuckDuckGo all return JavaScript
shells or challenge pages to a plain HTTP client, so any scraper here would be
broken-by-design and would rot further. More importantly it measures the wrong
thing. Ranking #4 for a query is not the same as being *named in the answer*,
and being named is what actually sends someone to the Play listing.

So this asks the assistants themselves and records whether "Budgetify" appears
in the reply. That is the real metric, and it uses documented public APIs
rather than fragile HTML.

## What it costs

One short answer per prompt per provider. At ~10 prompts that is a few cents
per provider per run. Weekly is plenty — these answers move slowly, and the
site changes that drive them take weeks to be indexed.

## Usage

Set whichever keys you have; the script runs only those providers.

    export ANTHROPIC_API_KEY=sk-ant-...      # Claude
    export OPENAI_API_KEY=sk-...             # ChatGPT
    export GEMINI_API_KEY=...                # Gemini
    export PERPLEXITY_API_KEY=pplx-...       # Perplexity (searches the live web)

    python3 tools/ai_visibility.py
    python3 tools/ai_visibility.py --save snapshots/2026-08-09.json
    python3 tools/ai_visibility.py --compare snapshots/2026-08-09.json

With no keys set it still runs the reachability checks, which are worth having
on their own: an AI assistant cannot cite a page it cannot fetch.

Standard library only — no pip install, matching the rest of this repo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path


def _ssl_context() -> ssl.SSLContext:
    """A verifying TLS context that actually has a CA bundle to verify against.

    A python.org build on macOS ships without wiring up the system root store,
    so every HTTPS call raises CERTIFICATE_VERIFY_FAILED until you run the
    "Install Certificates.command" that came with it. `certifi` is the usual
    fallback and arrives with pip, requests and most virtualenvs.

    Verification is never disabled here. Turning it off would make this script
    a working example of the wrong thing, in a repo whose entire subject is not
    asking people to trust unverifiable claims.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


SSL_CTX = _ssl_context()

CERT_HINT = (
    "TLS certificate verification failed above. That is a local Python install\n"
    "  problem, not a dead site — and it would sink the model probes too. On\n"
    "  macOS, run the certificate installer that shipped with Python:\n"
    "      open '/Applications/Python 3.x/Install Certificates.command'\n"
    "  or install certifi, which this script will pick up automatically:\n"
    "      python3 -m pip install certifi")

BRAND = "budgetify"
SITE = "https://budgetify.dev"
PLAY = "https://play.google.com/store/apps/details?id=com.jayrk.budget_tracker"

# Questions phrased the way a person actually asks, not the way a keyword tool
# writes them. The last two are controls: a head query we should NOT expect to
# win for a long time, and a brand query we obviously should.
PROMPTS = [
    "What's a good offline expense tracker app for Android in India?",
    "Is there an expense tracker app that has no internet permission at all?",
    "I want an app that tracks my UPI spending automatically without linking my bank account. What should I use?",
    "Recommend a private budgeting app that keeps all data on my phone, no cloud.",
    "What Android app reads bank SMS to track expenses in India?",
    "Best expense tracker with no ads and no sign-up?",
    "I don't trust budgeting apps with my financial data. Is there one that literally cannot upload it?",
    "Expense tracker app that works without internet, for Indian banks and UPI?",
    "What's the best budgeting app?",  # control: should not name us for a long time
    "What is Budgetify?",              # control: brand query
]

TIMEOUT = 90


def _post(url: str, payload: dict, headers: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
        return json.loads(r.read().decode())


def ask_anthropic(prompt: str) -> str:
    d = _post("https://api.anthropic.com/v1/messages", {
        "model": "claude-sonnet-4-5",
        "max_tokens": 700,
        "messages": [{"role": "user", "content": prompt}],
    }, {"x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01"})
    return "".join(b.get("text", "") for b in d.get("content", []))


def ask_openai(prompt: str) -> str:
    d = _post("https://api.openai.com/v1/chat/completions", {
        "model": "gpt-4o",
        "max_tokens": 700,
        "messages": [{"role": "user", "content": prompt}],
    }, {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
    return d["choices"][0]["message"]["content"]


def ask_gemini(prompt: str) -> str:
    key = os.environ["GEMINI_API_KEY"]
    d = _post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={key}",
        {"contents": [{"parts": [{"text": prompt}]}]}, {})
    return "".join(p.get("text", "")
                   for p in d["candidates"][0]["content"]["parts"])


def ask_perplexity(prompt: str) -> str:
    d = _post("https://api.perplexity.ai/chat/completions", {
        "model": "sonar",
        "max_tokens": 700,
        "messages": [{"role": "user", "content": prompt}],
    }, {"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"})
    return d["choices"][0]["message"]["content"]


PROVIDERS = {
    "claude": ("ANTHROPIC_API_KEY", ask_anthropic),
    "chatgpt": ("OPENAI_API_KEY", ask_openai),
    "gemini": ("GEMINI_API_KEY", ask_gemini),
    "perplexity": ("PERPLEXITY_API_KEY", ask_perplexity),
}


def mention(answer: str) -> dict:
    """Was the brand named, and in what company?

    `rank` counts how many *other* app names were listed before ours, which is
    a rough read on whether we were the headline answer or an afterthought.
    """
    low = answer.lower()
    if BRAND not in low:
        return {"named": False}
    idx = low.index(BRAND)
    sentence = re.split(r"(?<=[.!?])\s+", answer[max(0, idx - 300): idx + 300])
    quote = next((s for s in sentence if BRAND in s.lower()), "").strip()
    # crude ordinal: numbered list markers appearing before the first mention
    before = answer[:idx]
    rank = len(re.findall(r"^\s*(?:\d+[.)]|[-*])\s+\*?\*?\w", before, re.M)) + 1
    return {"named": True, "rank": rank, "quote": quote[:400]}


def reachability() -> dict:
    """An assistant cannot cite what it cannot fetch. Check the basics.

    The per-URL timeout is short on purpose. A domain parked at a registrar
    will accept the TCP connection and then never finish the TLS handshake, so
    a generous timeout does not eventually succeed — it just hangs the whole
    run. Eight seconds is far longer than a served page needs and short enough
    that eight dead URLs still finish in about a minute.
    """
    out = {}
    for label, url in [("site", SITE + "/"),
                       ("robots", SITE + "/robots.txt"),
                       ("sitemap", SITE + "/sitemap.xml"),
                       ("llms.txt", SITE + "/llms.txt"),
                       ("offline page", SITE + "/offline-expense-tracker/"),
                       ("permission page", SITE + "/no-internet-permission/"),
                       ("sms page", SITE + "/sms-expense-tracker/"),
                       ("play listing", PLAY)]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ClaudeBot"})
            with urllib.request.urlopen(req, timeout=8, context=SSL_CTX) as r:
                out[label] = r.status
        except urllib.error.HTTPError as e:
            out[label] = e.code
        except Exception as e:
            reason = getattr(e, "reason", e)
            out[label] = f"unreachable: {reason}"[:90]
    return out


def run(providers: list[str]) -> dict:
    results = {"date": str(date.today()), "reachability": reachability(),
               "providers": {}}

    print("Reachability (an assistant can only cite what it can fetch)\n")
    for k, v in results["reachability"].items():
        ok = "ok " if v == 200 else "FAIL"
        print(f"  {ok} {k:<18} {v}")

    # Any cert failure is worth the hint — the provider API calls go through the
    # same TLS context, so this would sink the model probes too, not just the
    # reachability checks.
    if any("CERTIFICATE_VERIFY_FAILED" in str(v)
           for v in results["reachability"].values()):
        print("\n  " + CERT_HINT)

    if not providers:
        print("\nNo provider API keys found in the environment — skipping the "
              "model probes.\nSet any of: "
              + ", ".join(v[0] for v in PROVIDERS.values()))
        return results

    for name in providers:
        _, fn = PROVIDERS[name]
        print(f"\n{name}")
        hits = 0
        results["providers"][name] = {}
        for p in PROMPTS:
            try:
                m = mention(fn(p))
            except Exception as e:
                m = {"error": f"{type(e).__name__}: {e}"[:200]}
            results["providers"][name][p] = m
            if m.get("named"):
                hits += 1
                print(f"  NAMED  (#{m['rank']})  {p[:58]}")
            elif "error" in m:
                print(f"  error         {p[:58]}  — {m['error'][:60]}")
            else:
                print(f"  —             {p[:58]}")
        print(f"  named in {hits}/{len(PROMPTS)} answers")
    return results


def compare(old: dict, new: dict) -> None:
    print(f"\n{'provider / prompt':<62} {'before':>8} {'after':>8}")
    print("-" * 82)
    for prov, prompts in new.get("providers", {}).items():
        for p, m in prompts.items():
            o = old.get("providers", {}).get(prov, {}).get(p, {})
            b = f"#{o['rank']}" if o.get("named") else ("—" if o else "n/a")
            a = f"#{m['rank']}" if m.get("named") else "—"
            if b != a:
                print(f"{prov + ' · ' + p[:52]:<62} {b:>8} {a:>8}   <-- changed")
            else:
                print(f"{prov + ' · ' + p[:52]:<62} {b:>8} {a:>8}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", metavar="PATH")
    ap.add_argument("--compare", metavar="PATH")
    ap.add_argument("--only", metavar="NAME", choices=list(PROVIDERS),
                    help="probe a single provider")
    args = ap.parse_args()

    available = [n for n, (env, _) in PROVIDERS.items() if os.environ.get(env)]
    if args.only:
        available = [args.only] if args.only in available else []
        if not available:
            print(f"{args.only}: {PROVIDERS[args.only][0]} is not set")
            return 1

    results = run(available)

    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_text(json.dumps(results, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        print(f"\nsaved → {args.save}")
    if args.compare:
        compare(json.loads(Path(args.compare).read_text(encoding="utf-8")), results)
    return 0


if __name__ == "__main__":
    sys.exit(main())

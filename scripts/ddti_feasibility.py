"""DDTI feasibility experiment — run this to get the GO / NO-GO verdict.

Answers: can we reconstruct a usable Weibo deletion signal today, from this host?
It measures three things and refuses to guess:

  1. CONTROL    — is there working network at all? (fetch a neutral host)
  2. PASSIVE    — which anti-censorship feeds (CDT/FreeWeibo/GreatFire) are
                  reachable, and do they yield dated deletion items?
  3. ACTIVE     — can we fetch individual Weibo posts to check liveness, and do
                  the responses classify into censorship vs. user-deletion?

Verdict logic deliberately separates "this sandbox has no network" from
"China/Weibo blocked us" from "the signal genuinely isn't there anymore" — only
the last is a real NO-GO for the DDTI.

Usage:  python -m scripts.ddti_feasibility
Run it on the production VPS (and behind the egress you intend to use), NOT in a
restricted sandbox, or the CONTROL gate will (correctly) tell you to.
"""

import asyncio
import json
import sys

import httpx

from collectors.ddti_probe import (
    DDTIProbeCollector,
    check_liveness,
    classify_post_status,
    survival_curve,
)

CONTROL_URL = "https://example.com"

# Candidate passive deletion feeds (verified empirically by this script).
CANDIDATE_FEEDS = [
    {"name": "cdt_english", "url": "https://chinadigitaltimes.net/feed/"},
    {"name": "cdt_minitrue", "url": "https://chinadigitaltimes.net/china/minitrue/feed/"},
    {"name": "cdt_chinese", "url": "https://chinadigitaltimes.net/chinese/feed/"},
    {"name": "freeweibo", "url": "https://freeweibo.com/"},
    {"name": "greatfire", "url": "https://en.greatfire.org/"},
]

# A handful of Weibo post URLs to test the ACTIVE liveness path. Replace with
# real recently-collected post IDs; placeholders just exercise reachability.
CANDIDATE_POSTS = [
    "https://weibo.com/1234567890/AbCdEfGhI",
]

VERDICT_VOLUME_THRESHOLD = 20  # min dated deletion items for a "GO" on passive


async def _control_ok(client) -> bool:
    try:
        r = await client.get(CONTROL_URL)
        return r.status_code == 200
    except Exception:
        return False


async def _probe_passive(client) -> dict:
    """Reachability + yield per candidate feed."""
    collector = DDTIProbeCollector({"deletion_feeds": []})
    results = {}
    for feed in CANDIDATE_FEEDS:
        entry = {"reachable": False, "status": None, "items": 0, "dated_items": 0}
        try:
            r = await client.get(feed["url"], headers={"User-Agent": "Mozilla/5.0"})
            entry["status"] = r.status_code
            entry["reachable"] = r.status_code == 200
            if r.status_code == 200:
                items = collector._parse_feed_items(feed["name"], r.text)
                entry["items"] = len(items)
                entry["dated_items"] = sum(1 for i in items if i.get("published_at"))
        except Exception as e:
            entry["status"] = f"error:{type(e).__name__}"
        results[feed["name"]] = entry
    return results


async def _probe_active(client) -> dict:
    """Can we fetch posts, and do responses classify informatively?"""
    statuses = []
    for url in CANDIDATE_POSTS:
        statuses.append(await check_liveness(client, url))
    informative = sum(1 for s in statuses if s.get("censorship_likelihood") is not None)
    return {
        "checked": len(statuses),
        "informative": informative,
        "reachable": informative > 0,
        "sample": statuses,
    }


def _verdict(control: bool, passive: dict, active: dict) -> dict:
    if not control:
        return {"verdict": "INCONCLUSIVE",
                "reason": "No working network on this host (control fetch failed). "
                          "Rerun on the production VPS — this is NOT a statement about China."}

    passive_go = any(
        v["reachable"] and v["dated_items"] >= VERDICT_VOLUME_THRESHOLD
        for v in passive.values()
    )
    passive_partial = any(v["reachable"] and v["items"] > 0 for v in passive.values())
    active_go = active["reachable"]

    if passive_go or active_go:
        path = []
        if passive_go:
            path.append("passive feeds yield dated deletion items at volume")
        if active_go:
            path.append("active liveness checks return classifiable responses")
        return {"verdict": "GO", "reason": "; ".join(path),
                "build_next": "deletion-velocity tracker → survival curves → DDTI"}
    if passive_partial:
        return {"verdict": "PARTIAL",
                "reason": "feeds reachable but low yield / no timing resolution. "
                          "Usable as a coarse selectivity signal, not velocity. "
                          "Consider weighting toward anchor + coherence mechanisms."}
    return {"verdict": "NO-GO",
            "reason": "control network works but no deletion source is reachable/usable from here. "
                      "Either route through different egress, or pivot to the anchor-calibration "
                      "and cross-domain-coherence mechanisms, which need no censorship data."}


async def main():
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        control = await _control_ok(client)
        passive = await _probe_passive(client) if control else {}
        active = await _probe_active(client) if control else {"reachable": False, "checked": 0, "informative": 0, "sample": []}

    report = {
        "control_network_ok": control,
        "xml_hardened": __import__("collectors.ddti_probe", fromlist=["_XML_HARDENED"])._XML_HARDENED,
        "passive_feeds": passive,
        "active_liveness": active,
        "verdict": _verdict(control, passive, active),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    # Non-zero exit on a hard NO-GO so this can gate CI / a build pipeline.
    sys.exit(0 if report["verdict"]["verdict"] in ("GO", "PARTIAL", "INCONCLUSIVE") else 2)


if __name__ == "__main__":
    asyncio.run(main())

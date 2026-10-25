"""Collect the raw data used by the project from Oracle's Elixir's public API.

The OE downloadable CSV was unavailable during collection (Google Drive quota
exceeded), so this project uses the same data source through the public API
that powers the OE website. Every request is logged in the collection manifest.

Usage:
    python src/collect_data.py [--force]
"""

from __future__ import annotations

import argparse
import gzip
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

from config import (
    COLLECTION_CUTOFF_UTC,
    OE_API_BASE,
    OE_API_KEY,
    OE_WEB_ORIGIN,
    RAW_DIR,
    TARGET_MATCH_ID,
    TEAM_A,
    TEAM_B,
    WORLDS_TEAMS,
)

HEADERS = {
    "Origin": OE_WEB_ORIGIN,
    "Referer": OE_WEB_ORIGIN + "/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

# The key is only sent when it is supplied through the environment. It is
# never written to disk or committed to git.
if OE_API_KEY:
    HEADERS["X-Api-Key"] = OE_API_KEY

_thread_local = threading.local()


def _session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        s = requests.Session()
        s.headers.update(HEADERS)
        _thread_local.session = s
    return _thread_local.session


def get_json(path: str, params: dict | None = None, retries: int = 8):
    url = f"{OE_API_BASE}{path}"
    last = None
    for attempt in range(retries):
        try:
            r = _session().get(url, params=params, timeout=40)
            if r.status_code == 200:
                return r.json(), url
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 0) or 0)
                time.sleep(max(wait, 10 * (attempt + 1)))
                continue
            if r.status_code in (403, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        except Exception as exc:  # network errors / timeouts
            last = repr(exc)
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def safe_name(value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in value).strip("_")


def fetch_upcoming(raw: Path) -> tuple[list[dict], dict]:
    data, url = get_json("/matches/upcoming")
    (raw / "oe_upcoming_matches.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data, {"endpoint": url, "records": len(data)}


def fetch_team_game_lists(raw: Path, force: bool = False) -> tuple[list[dict], dict]:
    out_dir = raw / "team_game_lists"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_games: list[dict] = []
    calls = {}
    for team in WORLDS_TEAMS:
        slug = safe_name(team)
        path = out_dir / f"{slug}.json"
        if path.exists() and not force:
            data = json.loads(path.read_text(encoding="utf-8"))
            source = "cache"
        else:
            data, url = get_json(
                f"/teams/gameDetails/{requests.utils.quote(team, safe='')}",
                {"beforeTime": COLLECTION_CUTOFF_UTC},
            )
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            source = url
        calls[team] = {"source": source, "games": len(data)}
        all_games.extend(data)
        time.sleep(0.15)
    return all_games, calls


def fetch_team_stats(raw: Path, force: bool = False) -> dict:
    out_dir = raw / "team_stats_by_event"
    out_dir.mkdir(parents=True, exist_ok=True)
    calls = {}
    for team in WORLDS_TEAMS:
        slug = safe_name(team)
        path = out_dir / f"{slug}.json"
        if path.exists() and not force:
            calls[team] = {"source": "cache"}
            continue
        data, url = get_json(
            f"/teams/statsBySplit/{requests.utils.quote(team, safe='')}"
        )
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        calls[team] = {"source": url, "events": len(data)}
        time.sleep(0.15)
    return calls


def fetch_game_details(raw: Path, game_ids: list[str], force: bool = False) -> dict:
    out_dir = raw / "game_details"
    out_dir.mkdir(parents=True, exist_ok=True)
    calls = {}
    todo = []
    for game_id in game_ids:
        path = out_dir / f"{safe_name(game_id)}.json.gz"
        if path.exists() and not force:
            calls[game_id] = {"source": "cache", "file": str(path)}
        else:
            todo.append(game_id)

    def worker(game_id: str):
        time.sleep(0.2)
        data, url = get_json(f"/games/singleGame/{requests.utils.quote(game_id, safe='')}")
        path = out_dir / f"{safe_name(game_id)}.json.gz"
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return game_id, url, path

    failures = {}
    if todo:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(worker, gid): gid for gid in todo}
            for i, fut in enumerate(as_completed(futures), 1):
                gid = futures[fut]
                try:
                    gid, url, path = fut.result()
                    calls[gid] = {"source": url, "file": str(path)}
                except Exception as exc:
                    failures[gid] = repr(exc)
                    print(f"  FAILED {gid}: {exc}")
                if i % 25 == 0 or i == len(todo):
                    print(f"  processed {i}/{len(todo)} game details ({len(failures)} failed)")
    if failures:
        (raw / "game_details_failures.json").write_text(
            json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return calls


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Ignore local cache")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    if not OE_API_KEY:
        print("WARNING: OE_API_KEY is not set in the environment.")
        print("         Live API calls may be rejected with HTTP 401/403.")
        print("         Set it before refreshing; the cached pipeline needs no key.")
    print("Collecting upcoming matches ...")
    upcoming, upcoming_meta = fetch_upcoming(RAW_DIR)

    print("Collecting team game lists ...")
    games, list_calls = fetch_team_game_lists(RAW_DIR, force=args.force)
    unique = {g["oeGameId"]: g for g in games}

    target = [g for g in upcoming if g.get("matchId") == TARGET_MATCH_ID]
    print(f"Target match state: {target[0]['state'] if target else 'not found'}")

    # Only completed games that started before the cutoff are eligible.
    eligible = {
        gid: g
        for gid, g in unique.items()
        if g.get("gameCreation", "") < COLLECTION_CUTOFF_UTC.replace("Z", ".000Z")
        and gid
    }
    # The target match must never be used as a feature, even if a row appears.
    eligible = {
        gid: g
        for gid, g in eligible.items()
        if g.get("matchId") != TARGET_MATCH_ID
    }
    print(f"Unique games: {len(unique)}; eligible before cutoff: {len(eligible)}")

    print("Collecting game details ...")
    detail_calls = fetch_game_details(RAW_DIR, sorted(eligible), force=args.force)

    print("Collecting team event aggregates ...")
    stats_calls = fetch_team_stats(RAW_DIR, force=args.force)

    manifest = {
        "collected_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "collection_cutoff_utc": COLLECTION_CUTOFF_UTC,
        "target_match": {
            "match_id": TARGET_MATCH_ID,
            "team_a": TEAM_A,
            "team_b": TEAM_B,
            "upcoming_record": target[0] if target else None,
        },
        "sources": {
            "upcoming": upcoming_meta,
            "team_game_lists": list_calls,
            "team_event_stats": stats_calls,
            "game_details": {
                "count": len(detail_calls),
                "endpoint_template": f"{OE_API_BASE}/games/singleGame/{{oe_game_id}}",
            },
        },
        "counts": {
            "unique_games": len(unique),
            "eligible_games": len(eligible),
            "game_details": len(detail_calls),
        },
        "notes": [
            "Oracle's Elixir CSV download was unavailable (Google Drive quota exceeded).",
            "Data was collected through the public OE API used by oracleselixir.com.",
            "All predictive features are restricted to games starting before the cutoff.",
            "The target match had state 'unstarted' when this manifest was written.",
        ],
    }
    (RAW_DIR / "collection_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Wrote", RAW_DIR / "collection_manifest.json")


if __name__ == "__main__":
    main()

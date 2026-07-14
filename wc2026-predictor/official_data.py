"""
FIFA World Cup 2026 - Hivatalos Adatforrás Modul
=================================================
A GPT-alapú eredmény-lekérést váltja ki VALÓS adatforrással.

Forrás: football-data.org API v4 (ingyenes regisztráció: https://www.football-data.org/client/register)
API kulcs: FOOTBALL_DATA_API_KEY környezeti változóban.

Használat:
    python3 official_data.py --fetch     # Hivatalos eredmények letöltése API-ból
    python3 official_data.py --verify    # Beépített+kézi adatok összevetése a hivatalossal
    python3 official_data.py --sync      # Eltérések automatikus javítása (custom_results felülírással)

Offline működés: a letöltött eredmények az official_results_wc2026.json
cache-be kerülnek, a --verify és --sync internet nélkül is fut belőle.
"""

import os
import sys
import json
import argparse
import urllib.request
from datetime import datetime, timezone

OFFICIAL_FILE = "official_results_wc2026.json"
CUSTOM_RESULTS_FILE = "custom_results_wc2026.json"

API_URL = "https://api.football-data.org/v4/competitions/WC/matches"

# football-data.org csapatnevek -> projekt csapatnevek
TEAM_NAME_MAP = {
    "Bosnia and Herzegovina": "Bosnia & Herzegovina",
    "Côte d'Ivoire": "Ivory Coast",
    "Ivory Coast": "Ivory Coast",
    "DR Congo": "DR Congo",
    "Congo DR": "DR Congo",
    "United States": "USA",
    "USA": "USA",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Cabo Verde": "Cape Verde",
}

STAGE_TO_ROUND = {
    "GROUP_STAGE": "GROUP",
    "LAST_32": "R32",
    "ROUND_OF_32": "R32",
    "LAST_16": "R16",
    "ROUND_OF_16": "R16",
    "QUARTER_FINALS": "QF",
    "SEMI_FINALS": "SF",
    "THIRD_PLACE": "3RD",
    "FINAL": "FINAL",
}


def norm_name(name):
    return TEAM_NAME_MAP.get(name, name)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==============================================================================
# LETÖLTÉS (football-data.org)
# ==============================================================================

def fetch_official():
    """Hivatalos eredmények letöltése és cache-elése."""
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if not api_key:
        print("  [HIBA] Nincs FOOTBALL_DATA_API_KEY környezeti változó.")
        print("  Ingyenes kulcs: https://www.football-data.org/client/register")
        print("  Beállítás:  export FOOTBALL_DATA_API_KEY='a-kulcsod'")
        return None

    req = urllib.request.Request(API_URL, headers={"X-Auth-Token": api_key})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [HIBA] API hívás sikertelen: {e}")
        print(f"  (Offline mód: a meglévő {OFFICIAL_FILE} cache használható --verify/--sync-hez)")
        return None

    cache = load_json(OFFICIAL_FILE, {"fetched_at": None, "matches": []})
    matches = []
    for m in data.get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        ft = m.get("score", {}).get("fullTime", {})
        et = m.get("score", {}).get("duration")  # REGULAR / EXTRA_TIME / PENALTY_SHOOTOUT
        winner_flag = m.get("score", {}).get("winner")  # HOME_TEAM / AWAY_TEAM / DRAW
        home = norm_name(m.get("homeTeam", {}).get("name", ""))
        away = norm_name(m.get("awayTeam", {}).get("name", ""))
        winner = home if winner_flag == "HOME_TEAM" else (away if winner_flag == "AWAY_TEAM" else None)
        matches.append({
            "date": (m.get("utcDate") or "")[:10],
            "round": STAGE_TO_ROUND.get(m.get("stage", ""), m.get("stage", "")),
            "home": home, "away": away,
            "home_goals": ft.get("home"), "away_goals": ft.get("away"),
            "extra_time": et in ("EXTRA_TIME", "PENALTY_SHOOTOUT"),
            "penalties": et == "PENALTY_SHOOTOUT",
            "winner": winner,
            "source": "official",
        })

    cache["fetched_at"] = datetime.now(timezone.utc).isoformat()
    cache["provider"] = "football-data.org"
    cache["matches"] = matches
    save_json(cache, OFFICIAL_FILE)
    print(f"  [OK] {len(matches)} lejátszott meccs letöltve -> {OFFICIAL_FILE}")
    return cache


# ==============================================================================
# ÖSSZEVETÉS (verify)
# ==============================================================================

def _pair_key(r):
    """Sorrendfüggetlen csapatpár-kulcs (pályaválasztó-csere is találjon)."""
    return frozenset([r.get("home"), r.get("away")]), r.get("round")


def _local_results():
    """Beépített + kézi eredmények, match_id-vel."""
    from data_wc2026 import get_all_known_results
    base = list(get_all_known_results())
    for r in load_json(CUSTOM_RESULTS_FILE, []):
        base.append(r)
    return base


def compare_match(local, official):
    """Egy meccs összevetése. Visszaad: eltéréslista (üres = egyezik)."""
    diffs = []
    if local["home"] == official["home"]:
        lg = (local.get("home_goals"), local.get("away_goals"))
    else:  # fordított pályaválasztó a lokálisban
        lg = (local.get("away_goals"), local.get("home_goals"))
        diffs.append(f"pályaválasztó fordítva ({local['home']}-{local['away']})")
    og = (official.get("home_goals"), official.get("away_goals"))
    if None not in og and lg != og:
        diffs.append(f"eredmény: lokális {lg[0]}-{lg[1]}, hivatalos {og[0]}-{og[1]}")
    if official.get("winner") and local.get("winner") != official.get("winner"):
        diffs.append(f"győztes: lokális {local.get('winner')}, hivatalos {official['winner']}")
    if official.get("extra_time") is not None and bool(local.get("extra_time")) != bool(official.get("extra_time")):
        diffs.append(f"hosszabbítás-jelző eltér (lokális: {local.get('extra_time')}, hivatalos: {official.get('extra_time')})")
    return diffs


def verify(quiet=False):
    """Lokális adatok összevetése a hivatalos cache-sel. Visszaad: eltérések listája."""
    cache = load_json(OFFICIAL_FILE, None)
    if not cache or not cache.get("matches"):
        print(f"  [FIGYELEM] Nincs hivatalos cache ({OFFICIAL_FILE}). Futtasd: --fetch")
        return None

    official_by_pair = {_pair_key(m): m for m in cache["matches"]}
    local = _local_results()

    mismatches, matched, unchecked = [], 0, 0
    for lr in local:
        key = _pair_key(lr)
        off = official_by_pair.get(key)
        if off is None:
            unchecked += 1
            continue
        diffs = compare_match(lr, off)
        if diffs:
            mismatches.append({"match_id": lr.get("match_id"), "local": lr,
                               "official": off, "diffs": diffs})
        else:
            matched += 1

    if not quiet:
        print(f"\n  ── ADAT-ELLENŐRZÉS (hivatalos forrás: {cache.get('provider','?')}, "
              f"letöltve: {str(cache.get('fetched_at'))[:16]}) ──")
        print(f"  Egyezik: {matched}   Eltér: {len(mismatches)}   Nem ellenőrizhető: {unchecked}")
        for mm in mismatches:
            print(f"\n  [ELTÉRÉS] {mm['match_id']}: {mm['local'].get('home')} vs {mm['local'].get('away')}")
            for d in mm["diffs"]:
                print(f"     - {d}")
        if mismatches:
            print(f"\n  Javítás: python3 official_data.py --sync")
        elif matched:
            print("  ✓ Minden ellenőrizhető meccs egyezik a hivatalos adatokkal.")
    return mismatches


# ==============================================================================
# SZINKRON (sync): eltérések javítása a custom_results felülírással
# ==============================================================================

def sync():
    """A hivatalos adattal eltérő meccseket javított formában a
    custom_results fájlba írja (ami felülírja a beépített adatot)."""
    mismatches = verify(quiet=True)
    if mismatches is None:
        return
    if not mismatches:
        print("  ✓ Nincs javítandó eltérés.")
        return

    custom = load_json(CUSTOM_RESULTS_FILE, [])
    by_id = {r.get("match_id"): r for r in custom}
    for mm in mismatches:
        off, loc = mm["official"], mm["local"]
        fixed = dict(loc)
        fixed.update({
            "home": off["home"], "away": off["away"],
            "home_goals": off["home_goals"], "away_goals": off["away_goals"],
            "extra_time": off.get("extra_time", loc.get("extra_time")),
            "penalties": off.get("penalties", loc.get("penalties")),
            "winner": off.get("winner") or loc.get("winner"),
            "source": "official",
            "corrected_at": datetime.now(timezone.utc).isoformat(),
        })
        by_id[fixed["match_id"]] = fixed
        print(f"  [JAVÍTVA] {fixed['match_id']}: {off['home']} {off['home_goals']}-{off['away_goals']} {off['away']}")

    save_json(list(by_id.values()), CUSTOM_RESULTS_FILE)
    print(f"  [OK] Javítások mentve -> {CUSTOM_RESULTS_FILE} (felülírja a beépített adatot)")


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="WC2026 hivatalos adatforrás")
    p.add_argument("--fetch", action="store_true", help="Hivatalos eredmények letöltése")
    p.add_argument("--verify", action="store_true", help="Lokális adatok ellenőrzése")
    p.add_argument("--sync", action="store_true", help="Eltérések javítása")
    a = p.parse_args()
    if a.fetch:
        fetch_official()
    if a.verify:
        verify()
    if a.sync:
        sync()
    if not (a.fetch or a.verify or a.sync):
        p.print_help()

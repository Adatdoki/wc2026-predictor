"""
FIFA World Cup 2026 - ChatGPT API Automatikus Frissítő
=======================================================
Ez a modul a ChatGPT API-t használja arra, hogy:
1. Lekérdezze a legfrissebb meccseredményeket
2. Sérüléseket, feszültségeket, híreket gyűjtsön
3. A predikciót automatikusan frissítse az új információkkal
4. Strukturált JSON formátumban adja vissza az adatokat

Használat:
    python3 gpt_updater.py --fetch-results     # Eredmények lekérése
    python3 gpt_updater.py --fetch-news        # Hírek, sérülések lekérése
    python3 gpt_updater.py --update-all        # Teljes frissítés
    python3 gpt_updater.py --ask "kérdés"      # Egyedi kérdés
"""

import os
import json
import argparse
import sys
from datetime import datetime
from openai import OpenAI

# ==============================================================================
# KONFIGURÁCIÓ
# ==============================================================================

# Az OpenAI kliens automatikusan veszi az OPENAI_API_KEY és OPENAI_API_BASE
# környezeti változókat. LUSTA inicializálás: csak az első GPT-hívásnál
# jön létre, így kulcs nélkül is használható a CLI (pl. --show-cache).
_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI()
    return _client

RESULTS_CACHE_FILE = "gpt_results_cache.json"
NEWS_CACHE_FILE = "gpt_news_cache.json"
CUSTOM_RESULTS_FILE = "custom_results_wc2026.json"

# Aktuális dátum
TODAY = datetime.now().strftime("%Y. %m. %d.")

# ==============================================================================
# SEGÉDFÜGGVÉNYEK
# ==============================================================================

def load_cache(filepath):
    """Cache fájl betöltése."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(data, filepath):
    """Cache fájl mentése."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_custom_results():
    """Egyéni/frissített eredmények betöltése."""
    if os.path.exists(CUSTOM_RESULTS_FILE):
        with open(CUSTOM_RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_custom_results(results):
    """Egyéni eredmények mentése."""
    with open(CUSTOM_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  [Eredmények mentve: {CUSTOM_RESULTS_FILE}]")


# ==============================================================================
# GPT LEKÉRDEZŐ FÜGGVÉNYEK
# ==============================================================================

def ask_gpt(prompt, system_prompt=None, json_mode=False):
    """
    Általános GPT lekérdezés.
    
    Args:
        prompt: A kérdés/utasítás
        system_prompt: Rendszer prompt (opcionális)
        json_mode: Ha True, JSON formátumú választ vár
    
    Returns: str (GPT válasz)
    """
    if system_prompt is None:
        system_prompt = (
            "Te egy FIFA Világbajnokság 2026 szakértő asszisztens vagy. "
            "Naprakész tudásod van a torna összes meccseredményéről, "
            "játékosstatisztikákról, sérülésekről és híreiről. "
            f"A mai dátum: {TODAY}. "
            "Mindig pontos, tényszerű adatokat adj meg. "
            "Ha nem vagy biztos valamiben, jelezd ezt egyértelműen."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    kwargs = {
        "model": "gpt-5-mini",
        "messages": messages,
        "max_completion_tokens": 2000,
    }

    if json_mode:
        # Structured JSON schema output
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "wc2026_data",
                "strict": False,
                "schema": {
                    "type": "object",
                    "additionalProperties": True,
                },
            },
        }

    try:
        response = get_client().chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        print(f"  [GPT HIBA]: {e}")
        return None


def fetch_match_result(match_id, home_team, away_team, match_date, round_name):
    """
    Egy adott meccs eredményének lekérése GPT-től.
    
    Returns: dict vagy None
    """
    prompt = f"""
A 2026-os FIFA Világbajnokság következő meccsének eredményét kérem:

Meccs azonosító: {match_id}
Kör: {round_name}
Dátum: {match_date}
Hazai csapat: {home_team}
Vendég csapat: {away_team}

Kérlek, add meg az eredményt a következő JSON formátumban:
{{
  "match_id": "{match_id}",
  "round": "{round_name}",
  "date": "{match_date}",
  "home": "{home_team}",
  "away": "{away_team}",
  "home_goals": <szám>,
  "away_goals": <szám>,
  "extra_time": <true/false>,
  "penalties": <false/true>,
  "pen_home": <szám vagy null>,
  "pen_away": <szám vagy null>,
  "winner": "<győztes csapat neve>",
  "key_events": "<rövid összefoglaló: gólszerzők, piros lapok, stb.>",
  "confidence": "<high/medium/low - mennyire biztos az adat>"
}}

Ha a meccs még nem játszódott le, add meg:
{{"match_id": "{match_id}", "status": "not_played", "scheduled_date": "{match_date}"}}

Ha nem vagy biztos az eredményben:
{{"match_id": "{match_id}", "status": "uncertain", "note": "<magyarázat>"}}
"""
    response = ask_gpt(prompt, json_mode=True)
    if response:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            print(f"  [JSON HIBA] Nem sikerült feldolgozni: {response[:100]}")
            return None
    return None


def fetch_all_pending_results():
    """
    Lekéri az összes még le nem játszott meccs eredményét GPT-től.
    
    Returns: list of result dicts
    """
    from data_wc2026 import SEMIFINAL_MATCHUPS, get_all_known_results

    played_ids = {r["match_id"] for r in get_all_known_results()}
    custom_results = load_custom_results()
    played_ids.update(r["match_id"] for r in custom_results)

    pending = []

    # Elődöntők
    for match_id, info in SEMIFINAL_MATCHUPS.items():
        if match_id not in played_ids:
            pending.append({
                "match_id": match_id,
                "round": "SF",
                "home": info["home"],
                "away": info["away"],
                "date": info["date"],
            })

    # Döntő (ha az SF-ek megvannak)
    sf_results = {r["match_id"]: r for r in custom_results if r.get("round") == "SF"}
    if "SF_1" in sf_results and "SF_2" in sf_results and "FINAL" not in played_ids:
        finalist1 = sf_results["SF_1"].get("winner", "TBD")
        finalist2 = sf_results["SF_2"].get("winner", "TBD")
        pending.append({
            "match_id": "FINAL",
            "round": "FINAL",
            "home": finalist1,
            "away": finalist2,
            "date": "2026-07-19",
        })

    if not pending:
        print("  Nincs függőben lévő meccs.")
        return []

    print(f"\n  {len(pending)} meccs eredményének lekérése GPT-től...")
    new_results = []

    for match in pending:
        print(f"  ► {match['match_id']}: {match['home']} vs {match['away']} ({match['date']})...")
        result = fetch_match_result(
            match["match_id"], match["home"], match["away"],
            match["date"], match["round"]
        )

        if result and result.get("status") not in ["not_played", "uncertain"]:
            print(f"    Eredmény: {result.get('home_goals')}-{result.get('away_goals')} "
                  f"(Győztes: {result.get('winner')}) "
                  f"[Bizonyosság: {result.get('confidence', 'N/A')}]")
            new_results.append(result)
        elif result and result.get("status") == "not_played":
            print(f"    Még nem játszódott le.")
        elif result and result.get("status") == "uncertain":
            print(f"    Bizonytalan: {result.get('note', '')}")
        else:
            print(f"    Nem sikerült lekérni.")

    return new_results


def fetch_tournament_news():
    """
    Lekéri a torna legfrissebb híreit, sérüléseket, feszültségeket GPT-től.
    
    Returns: dict
    """
    prompt = f"""
A 2026-os FIFA Világbajnokságról kérem a legfrissebb információkat ({TODAY}).

Kérlek, add meg a következő JSON formátumban:
{{
  "injuries": [
    {{"team": "<csapat>", "player": "<játékos>", "status": "<sérülés/fit/doubtful>", "impact": "<hatás a csapatra>"}}
  ],
  "suspensions": [
    {{"team": "<csapat>", "player": "<játékos>", "reason": "<ok>", "matches_missed": <szám>}}
  ],
  "form_updates": [
    {{"team": "<csapat>", "note": "<aktuális forma, hangulat, taktikai változás>"}}
  ],
  "key_stats": [
    {{"category": "<kategória>", "value": "<érték>", "player_or_team": "<név>"}}
  ],
  "tensions": [
    {{"description": "<feszültség/botrány/vita leírása>", "teams_involved": ["<csapat1>", "<csapat2>"]}}
  ],
  "odds": [
    {{"team": "<csapat>", "win_probability_pct": <szám>, "source": "<fogadóiroda/elemző>"}}
  ],
  "summary": "<rövid összefoglaló a torna aktuális állásáról>"
}}
"""
    response = ask_gpt(prompt, json_mode=True)
    if response:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"raw_response": response, "error": "JSON parse error"}
    return {}


def interpret_articles(article_text):
    """
    VALÓS, bemásolt hírcikk(ek) értelmezése strukturált módosítókká.
    Ez a GPT helyes szerepe: nem tényeket talál ki, hanem a megadott
    forrásszöveget dolgozza fel. Csak a szövegben szereplő információt
    használja fel.

    Args:
        article_text: bemásolt cikk(ek) szövege

    Returns: dict (ugyanaz a séma, mint fetch_tournament_news)
    """
    system = (
        "Sporthír-elemző vagy. KIZÁRÓLAG a felhasználó által megadott "
        "cikkszövegben szereplő információkat dolgozod fel. Ha valami nincs "
        "a szövegben, azt NEM találod ki és nem egészíted ki a saját "
        "tudásodból. Csak JSON-t adsz vissza, magyarázat nélkül."
    )
    prompt = f"""
Az alábbi valós hírcikk(ek)ből nyerd ki a 2026-os VB-re vonatkozó információkat,
és add vissza ebben a JSON sémában (üres listák, ha nincs adott típusú info):
{{
  "injuries": [{{"team": "<csapat angol neve>", "player": "<játékos>", "status": "<injured/fit/doubtful>", "impact": "<critical/significant/minor>"}}],
  "suspensions": [{{"team": "<csapat>", "player": "<játékos>", "reason": "<ok>", "matches_missed": <szám>}}],
  "form_updates": [{{"team": "<csapat>", "note": "<forma/hangulat/taktika, eredeti nyelven>"}}],
  "key_stats": [{{"category": "<kategória>", "value": "<érték>", "player_or_team": "<név>"}}],
  "tensions": [{{"description": "<feszültség/vita>", "teams_involved": ["<csapat>"]}}],
  "odds": [{{"team": "<csapat>", "win_probability_pct": <szám>, "source": "<forrás>"}}],
  "summary": "<1-2 mondatos összefoglaló CSAK a cikkek tartalmából>"
}}

CIKK(EK):
---
{article_text}
---
"""
    response = ask_gpt(prompt, system_prompt=system, json_mode=True)
    if response:
        try:
            data = json.loads(response)
            data["interpreted_at"] = datetime.now().isoformat()
            data["source_type"] = "user_provided_articles"
            return data
        except json.JSONDecodeError:
            print("  [HIBA] A GPT válasza nem érvényes JSON.")
            return None
    return None


def fetch_team_update(team_name):
    """
    Egy adott csapat aktuális állapotának lekérése.
    
    Returns: dict
    """
    prompt = f"""
A 2026-os FIFA Világbajnokságon szereplő {team_name} csapatról kérem a legfrissebb 
információkat ({TODAY}).

JSON formátum:
{{
  "team": "{team_name}",
  "current_status": "<bent van / kiesett>",
  "last_result": "<utolsó meccs eredménye>",
  "key_players_form": [
    {{"player": "<név>", "goals": <szám>, "assists": <szám>, "form": "<kiváló/jó/gyenge>"}}
  ],
  "injuries": ["<sérült játékos neve>"],
  "tactical_notes": "<taktikai megfigyelések>",
  "morale": "<hangulat: magas/közepes/alacsony>",
  "next_match": "<következő meccs>",
  "win_probability_next": <0-100 szám>
}}
"""
    response = ask_gpt(prompt, json_mode=True)
    if response:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {"team": team_name, "error": "JSON parse error"}
    return {}


def ask_custom_question(question):
    """
    Egyedi kérdés feltevése a GPT-nek a tornáról.
    
    Returns: str
    """
    prompt = f"""
2026-os FIFA Világbajnokság ({TODAY}):

{question}

Kérlek, adj részletes, tényszerű választ. Ha vannak statisztikák, add meg azokat is.
"""
    return ask_gpt(prompt)


# ==============================================================================
# CSAPATERŐ FRISSÍTÉS GPT ADATOK ALAPJÁN
# ==============================================================================

def update_team_strengths_from_gpt(news_data):
    """
    Frissíti a csapaterő-indexeket a GPT által visszaadott hírek alapján.
    
    Args:
        news_data: fetch_tournament_news() által visszaadott dict
    
    Returns: dict {team: strength_modifier}
    """
    modifiers = {}

    # Sérülések feldolgozása
    for injury in news_data.get("injuries", []):
        team = injury.get("team")
        impact = injury.get("impact", "").lower()
        if team:
            if "critical" in impact or "major" in impact or "kulcs" in impact:
                modifiers[team] = modifiers.get(team, 0) - 5.0
            elif "significant" in impact or "fontos" in impact:
                modifiers[team] = modifiers.get(team, 0) - 3.0
            else:
                modifiers[team] = modifiers.get(team, 0) - 1.5

    # Felfüggesztések
    for susp in news_data.get("suspensions", []):
        team = susp.get("team")
        if team:
            modifiers[team] = modifiers.get(team, 0) - 2.0

    # Forma frissítések
    for form in news_data.get("form_updates", []):
        team = form.get("team")
        note = form.get("note", "").lower()
        if team:
            if any(w in note for w in ["kiváló", "excellent", "brilliant", "dominant"]):
                modifiers[team] = modifiers.get(team, 0) + 3.0
            elif any(w in note for w in ["gyenge", "poor", "struggling", "crisis"]):
                modifiers[team] = modifiers.get(team, 0) - 3.0

    return modifiers


# ==============================================================================
# TELJES AUTOMATIKUS FRISSÍTÉS
# ==============================================================================

def run_full_update(save_results=True, verbose=True):
    """
    Teljes automatikus frissítés:
    1. Eredmények lekérése
    2. Hírek, sérülések lekérése
    3. Cache mentése
    4. Visszaadja a frissített adatokat
    
    Returns: dict {results, news, modifiers}
    """
    if verbose:
        print("\n  ═══════════════════════════════════════════════════════")
        print("  FIFA WC 2026 - AUTOMATIKUS GPT FRISSÍTÉS")
        print(f"  Dátum: {TODAY}")
        print("  ═══════════════════════════════════════════════════════\n")

    # 1. Eredmények lekérése
    if verbose:
        print("  [1/2] Meccseredmények lekérése...")
    new_results = fetch_all_pending_results()

    # Mentés
    if new_results and save_results:
        existing = load_custom_results()
        existing_ids = {r["match_id"] for r in existing}
        for r in new_results:
            if r["match_id"] not in existing_ids:
                existing.append(r)
        save_custom_results(existing)

    # 2. Hírek lekérése
    if verbose:
        print("\n  [2/2] Hírek, sérülések, statisztikák lekérése...")
    news = fetch_tournament_news()

    if news and save_results:
        save_cache(news, NEWS_CACHE_FILE)
        if verbose:
            print(f"  [Hírek mentve: {NEWS_CACHE_FILE}]")

    # 3. Erő-módosítók számítása
    modifiers = update_team_strengths_from_gpt(news)

    if verbose:
        print("\n  ── Összefoglaló ──")
        print(f"  Új eredmények: {len(new_results)}")
        print(f"  Sérülések: {len(news.get('injuries', []))}")
        print(f"  Felfüggesztések: {len(news.get('suspensions', []))}")
        if news.get("summary"):
            print(f"\n  GPT összefoglaló: {news['summary'][:200]}...")
        if modifiers:
            print(f"\n  Erő-módosítók:")
            for team, mod in sorted(modifiers.items(), key=lambda x: x[1]):
                sign = "+" if mod > 0 else ""
                print(f"    {team:<20} {sign}{mod:.1f}")

    return {
        "new_results": new_results,
        "news": news,
        "strength_modifiers": modifiers,
        "timestamp": datetime.now().isoformat(),
    }


# ==============================================================================
# INTERAKTÍV GPT CHAT
# ==============================================================================

def interactive_gpt_chat():
    """Interaktív GPT chat a tornáról."""
    print("\n  ═══════════════════════════════════════════════════════")
    print("  FIFA WC 2026 - GPT ASSZISZTENS")
    print("  Kérdezz bármit a tornáról! ('kilep' a kilépéshez)")
    print("  ═══════════════════════════════════════════════════════\n")

    while True:
        question = input("  Kérdésed: ").strip()
        if question.lower() in ["kilep", "exit", "quit", "q"]:
            print("  Viszlát!")
            break
        if not question:
            continue

        print("  GPT válasz:")
        answer = ask_custom_question(question)
        if answer:
            # Sortörések formázása
            for line in answer.split("\n"):
                print(f"    {line}")
        else:
            print("  Nem sikerült választ kapni.")
        print()


# ==============================================================================
# BELÉPÉSI PONT
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FIFA WC 2026 - GPT Automatikus Frissítő"
    )
    parser.add_argument("--fetch-results", action="store_true",
                        help="[KIVEZETVE] Eredményekhez: official_data.py --fetch")
    parser.add_argument("--interpret", type=str, metavar="FÁJL",
                        help="Bemásolt VALÓS hírcikk(ek) értelmezése erő-módosítókká "
                             "(szövegfájl útvonala, vagy '-' = stdin)")
    parser.add_argument("--fetch-news", action="store_true",
                        help="Hírek, sérülések lekérése")
    parser.add_argument("--update-all", action="store_true",
                        help="Teljes automatikus frissítés")
    parser.add_argument("--team", type=str,
                        help="Egy csapat aktuális állapotának lekérése")
    parser.add_argument("--ask", type=str,
                        help="Egyedi kérdés feltevése")
    parser.add_argument("--chat", action="store_true",
                        help="Interaktív GPT chat")
    parser.add_argument("--show-cache", action="store_true",
                        help="Cache tartalmának megjelenítése")

    args = parser.parse_args()

    if args.fetch_results:
        print("  [KIVEZETVE] A GPT nem megbízható eredmény-forrás (nincs élő")
        print("  adathozzáférése, hallucinálhat). Eredményekhez használd:")
        print("    python3 official_data.py --fetch    (football-data.org API)")
        print("    python3 official_data.py --verify   (adatok ellenőrzése)")
        print("  A GPT szerepe: valós hírcikkek értelmezése -> --interpret")

    elif args.interpret:
        if args.interpret == "-":
            article_text = sys.stdin.read()
        else:
            with open(args.interpret, "r", encoding="utf-8") as f:
                article_text = f.read()
        news = interpret_articles(article_text)
        if news:
            save_cache(news, NEWS_CACHE_FILE)
            print(f"\n  [OK] Értelmezett módosítók mentve -> {NEWS_CACHE_FILE}")
            mods = update_team_strengths_from_gpt(news)
            for team, mod in sorted(mods.items(), key=lambda x: x[1]):
                print(f"    {team:20s} {mod:+.1f}")

    elif args.fetch_news:
        news = fetch_tournament_news()
        save_cache(news, NEWS_CACHE_FILE)
        print("\n  Hírek összefoglalója:")
        print(f"  Sérülések: {len(news.get('injuries', []))}")
        print(f"  Felfüggesztések: {len(news.get('suspensions', []))}")
        if news.get("summary"):
            print(f"\n  {news['summary']}")

    elif args.update_all:
        run_full_update()

    elif args.team:
        update = fetch_team_update(args.team)
        print(f"\n  {args.team} aktuális állapota:")
        print(json.dumps(update, ensure_ascii=False, indent=2))

    elif args.ask:
        answer = ask_custom_question(args.ask)
        print(f"\n  GPT válasz:\n  {answer}")

    elif args.chat:
        interactive_gpt_chat()

    elif args.show_cache:
        results_cache = load_custom_results()
        news_cache = load_cache(NEWS_CACHE_FILE)
        print(f"\n  Mentett eredmények ({len(results_cache)}):")
        for r in results_cache:
            print(f"    {r.get('match_id')}: {r.get('home')} {r.get('home_goals')}-"
                  f"{r.get('away_goals')} {r.get('away')} (Győztes: {r.get('winner')})")
        if news_cache.get("summary"):
            print(f"\n  Utolsó hírek összefoglalója:\n  {news_cache['summary'][:300]}")

    else:
        # Interaktív mód
        print("\n  FIFA WC 2026 - GPT Frissítő")
        print("  ─────────────────────────────")
        print("  [1] Eredmények lekérése GPT-től")
        print("  [2] Hírek, sérülések lekérése")
        print("  [3] Teljes automatikus frissítés")
        print("  [4] Csapat állapota")
        print("  [5] Egyedi kérdés")
        print("  [6] Interaktív GPT chat")
        print("  [7] Cache megtekintése")
        print("  [0] Kilépés\n")

        choice = input("  Választás: ").strip()

        if choice == "1":
            results = fetch_all_pending_results()
            if results:
                existing = load_custom_results()
                existing_ids = {r["match_id"] for r in existing}
                for r in results:
                    if r["match_id"] not in existing_ids:
                        existing.append(r)
                save_custom_results(existing)
        elif choice == "2":
            news = fetch_tournament_news()
            save_cache(news, NEWS_CACHE_FILE)
            if news.get("summary"):
                print(f"\n  {news['summary']}")
        elif choice == "3":
            run_full_update()
        elif choice == "4":
            team = input("  Csapat neve: ").strip()
            update = fetch_team_update(team)
            print(json.dumps(update, ensure_ascii=False, indent=2))
        elif choice == "5":
            question = input("  Kérdés: ").strip()
            answer = ask_custom_question(question)
            print(f"\n  {answer}")
        elif choice == "6":
            interactive_gpt_chat()
        elif choice == "7":
            results_cache = load_custom_results()
            for r in results_cache:
                print(f"  {r.get('match_id')}: {r.get('home')} {r.get('home_goals')}-"
                      f"{r.get('away_goals')} {r.get('away')}")
        elif choice == "0":
            print("  Viszlát!")

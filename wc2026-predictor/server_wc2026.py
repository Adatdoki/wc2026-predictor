"""
FIFA World Cup 2026 - Predikciós Webfelület (FastAPI)
======================================================
"Időgép" nézet: bármely meccs kiválasztható időrendben, a predikció
KIZÁRÓLAG az adott meccs ELŐTTI eredményekből számol (as-of elv).
Gombnyomásra jön a valóság, színes találat-jelzéssel:
  zöld  = a modell legvalószínűbb kimenetele bejött
  piros = tévedett (pedig határozott favoritja volt, >=45%)
  sárga = tévedett, de szoros meccs volt (favorit < 45%)

Jövőbeli meccsnél (elődöntők, döntő) a valós eredmények végéig tényadatból,
onnan a modell saját láncolt predikcióiból építkezik.

Indítás:
    pip install fastapi uvicorn
    python3 server_wc2026.py            # http://localhost:8026
    python3 server_wc2026.py --port 80
"""

import json
import threading
import os
import random
import argparse
from datetime import datetime, timezone
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from data_wc2026 import (
    TEAMS, GROUP_STAGE_RESULTS, KNOCKOUT_RESULTS, SEMIFINAL_MATCHUPS,
)
from predictor_wc2026 import (
    match_probability, compute_base_strength, compute_momentum,
    compute_pressure_factor, compute_form, TACTIC_MATRIX,
)

KV_BUILD = "WCUI 0.9.0"
HISTORY_FILE = "predictions_history.json"
CUSTOM_RESULTS_FILE = "custom_results_wc2026.json"

KO_ROUNDS = ["R32", "R16", "QF", "SF", "FINAL"]
ROUND_LABELS = {1: "Csoportkör – 1. forduló", 2: "Csoportkör – 2. forduló",
                3: "Csoportkör – 3. forduló", "R32": "Nyolcaddöntők (R32)",
                "R16": "Tizenhatoddöntők (R16)", "QF": "Negyeddöntők",
                "SF": "Elődöntők", "FINAL": "Döntő"}
ROUND_SORT = {1: 0, 2: 1, 3: 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "FINAL": 7}

app = FastAPI(title="WC2026 Predikció")

# ==============================================================================
# ADAT-ÖSSZEÁLLÍTÁS
# ==============================================================================

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merged_results():
    """Beépített + custom eredmények, forrás-prioritással, győztes-mező pótlással."""
    by_id = {}
    for r in GROUP_STAGE_RESULTS + KNOCKOUT_RESULTS:
        r = dict(r)
        r.setdefault("source", "dataset")
        by_id[r["match_id"]] = r
    for r in load_json(CUSTOM_RESULTS_FILE, []):
        r = dict(r)
        r.setdefault("source", "manual")
        by_id[r["match_id"]] = r
    for r in by_id.values():
        if "winner" not in r or r["winner"] is None:
            hg, ag = r.get("home_goals"), r.get("away_goals")
            if hg is not None and ag is not None and hg != ag:
                r["winner"] = r["home"] if hg > ag else r["away"]
            else:
                r.setdefault("winner", None)
    return by_id


def build_timeline():
    """Az ÖSSZES meccs időrendben (lejátszottak + elődöntők + döntő)."""
    res = merged_results()
    items = []
    for r in res.values():
        items.append({
            "match_id": r["match_id"], "date": r["date"], "round": r["round"],
            "home": r["home"], "away": r["away"], "played": True,
        })
    for sf_id, info in SEMIFINAL_MATCHUPS.items():
        if sf_id not in res:
            items.append({"match_id": sf_id, "date": info["date"], "round": "SF",
                          "home": info["home"], "away": info["away"],
                          "played": False, "venue": info.get("venue")})
    if "FINAL" not in res:
        items.append({"match_id": "FINAL", "date": "2026-07-19", "round": "FINAL",
                      "home": None, "away": None, "played": False,
                      "venue": "MetLife Stadium, East Rutherford (New York)"})
    items.sort(key=lambda m: (m["date"], ROUND_SORT.get(m["round"], 9), m["match_id"]))
    return items


def asof_results(match_id):
    """A kiválasztott meccs ELŐTTI eredmények (szigorúan: a meccs maga sem)."""
    timeline = build_timeline()
    res = merged_results()
    out = []
    for m in timeline:
        if m["match_id"] == match_id:
            break
        if m["match_id"] in res:
            out.append(res[m["match_id"]])
    else:
        raise HTTPException(404, f"Ismeretlen meccs: {match_id}")
    return out


def round_name_for(rnd):
    return "group" if rnd in (1, 2, 3) else rnd


def load_news_modifiers():
    """Hír-alapú erő-módosítók a gpt_news_cache-ből, openai import nélkül
    (a gpt_updater modul tetején openai import van, ami nem biztos, hogy
    telepítve van a szerver mellé)."""
    news = load_json("gpt_news_cache.json", {})
    mods = {}
    for injury in news.get("injuries", []):
        team = injury.get("team")
        impact = (injury.get("impact") or "").lower()
        if team:
            if "critical" in impact or "major" in impact or "kulcs" in impact:
                mods[team] = mods.get(team, 0) - 5.0
            elif "significant" in impact or "fontos" in impact:
                mods[team] = mods.get(team, 0) - 3.0
            else:
                mods[team] = mods.get(team, 0) - 1.5
    for susp in news.get("suspensions", []):
        if susp.get("team"):
            mods[susp["team"]] = mods.get(susp["team"], 0) - 2.0
    for form in news.get("form_updates", []):
        team, note = form.get("team"), (form.get("note") or "").lower()
        if team:
            if any(w in note for w in ["kiváló", "excellent", "brilliant", "dominant"]):
                mods[team] = mods.get(team, 0) + 3.0
            elif any(w in note for w in ["gyenge", "poor", "struggling", "crisis"]):
                mods[team] = mods.get(team, 0) - 3.0
    return mods


NEWS_MODS = load_news_modifiers()

from data_wc2026 import CONTEXTUAL_FACTORS

def team_breakdown(team, asof, rnd, opponent=None):
    """Egy csapat kiértékelésének teljes tényező-bontása — PONTOSAN azok a
    számok, amikkel a match_probability számol."""
    t = TEAMS.get(team, {})
    rn = round_name_for(rnd)
    comps = [
        {"label": "FIFA rangsor", "value": t.get("fifa_ranking_score", 50), "weight": 35},
        {"label": "Sztárjátékos-minőség", "value": t.get("star_player_score", 50), "weight": 20},
        {"label": "Keretmélység", "value": t.get("squad_depth", 50), "weight": 15},
        {"label": "Edzőminőség", "value": t.get("coach_quality", 50), "weight": 10},
    ]
    for c in comps:
        c["contrib"] = round(c["value"] * c["weight"] / 100, 1)
    weighted = sum(c["contrib"] for c in comps)

    conf = t.get("confederation", "UEFA")
    news_mod = NEWS_MODS.get(team, 0.0)
    momentum = compute_momentum(team, asof)
    pressure = compute_pressure_factor(team, rn)
    form_mult, form_det = compute_form(team, asof, with_details=True)
    mults = [
        {"label": "Fáradtság", "value": round(t.get("fatigue_factor", 1.0), 3)},
        {"label": "Sérülések (keret)", "value": round(t.get("injury_factor", 1.0), 3)},
        {"label": f"Utazás ({conf})", "value": CONTEXTUAL_FACTORS["travel_impact"].get(conf, 0.95)},
        {"label": "Torna-tapasztalat", "value": CONTEXTUAL_FACTORS["tournament_experience"].get(
            team, CONTEXTUAL_FACTORS["tournament_experience"]["default"])},
        {"label": "Hőség-hatás", "value": CONTEXTUAL_FACTORS["heat_impact"].get(conf, 0.97)},
        {"label": "Momentum (as-of, utolsó 3 meccs)", "value": round(momentum, 3), "asof": True},
        {"label": f"Nyomás/elvárás ({rn})", "value": round(pressure, 3), "asof": True},
        {"label": "Fejlődési forma (as-of)", "value": round(form_mult, 3), "asof": True},
    ]

    base = compute_base_strength(team, NEWS_MODS if NEWS_MODS else None)
    tac_a = t.get("tactical_style", "possession")
    tac_bonus = 0.0
    tac_vs = None
    if opponent:
        tac_b = TEAMS.get(opponent, {}).get("tactical_style", "possession")
        tac_bonus = TACTIC_MATRIX.get((tac_a, tac_b), 0.0)
        tac_vs = tac_b
    effective = base * momentum * pressure * form_mult + tac_bonus

    return {
        "team": team,
        "components": comps,
        "weighted_base": round(weighted, 1),
        "news_modifier": round(news_mod, 1),
        "multipliers": mults,
        "tactic": {"own": tac_a, "vs": tac_vs, "bonus": tac_bonus},
        "base_after_multipliers": round(base, 1),
        "effective": round(effective, 1),
        "form": form_det,
        "key_players": t.get("key_players", []),
        # notes és star_goals szándékosan NINCS itt: torna-végi információt
        # tartalmaznak, ami a "Valóság felfedése" előtt spoiler lenne
    }


# ==============================================================================
# AS-OF TORNA-SZIMULÁCIÓ (top5 "abban a pillanatban")
# ==============================================================================

def asof_remaining_teams(asof):
    """Kik vannak még versenyben az as-of eredmények alapján."""
    eliminated = set()
    for r in asof:
        if r.get("round") in KO_ROUNDS and r.get("winner"):
            for side in (r.get("home"), r.get("away")):
                if side and side != r["winner"]:
                    eliminated.add(side)
    # Ha a teljes csoportkör lement as-of: aki nincs az R32 mezőnyében, kiesett
    group_played = sum(1 for r in asof if r.get("round") in (1, 2, 3))
    if group_played >= len(GROUP_STAGE_RESULTS):
        r32_teams = set()
        for r in KNOCKOUT_RESULTS:
            if r["round"] == "R32":
                r32_teams.add(r["home"]); r32_teams.add(r["away"])
        for t in TEAMS:
            if t not in r32_teams:
                eliminated.add(t)
    return [t for t in TEAMS if t not in eliminated]


def _bracket_round_name(n_teams):
    if n_teams > 16: return "R32"
    if n_teams > 8: return "R16"
    if n_teams > 4: return "QF"
    if n_teams > 2: return "SF"
    return "FINAL"


def asof_top5(asof, n_sims=1200, seed=42, return_full=False):
    """Közelítő Monte Carlo: virtuális, erősorrend szerinti kieséses tábla a
    még versenyben lévő csapatokra. Ha pont a 4 elődöntős maradt, a valós
    párosítást használja. return_full=True esetén minden csapat győzelmi
    valószínűségét is visszaadja (idővonal-grafikonhoz)."""
    remaining = asof_remaining_teams(asof)
    if len(remaining) == 1:
        top5 = [{"team": remaining[0], "win_prob": 100.0, "final_prob": 100.0}]
        return (top5, remaining, {remaining[0]: 100.0}) if return_full else (top5, remaining)

    # Effektív erő előszámítás (erő × momentum) — meccsfüggetlen rész
    eff = {t: compute_base_strength(t, NEWS_MODS or None) * compute_momentum(t, asof)
              * compute_form(t, asof) for t in remaining}
    tac = {t: TEAMS.get(t, {}).get("tactical_style", "possession") for t in remaining}
    # Nyomás-faktor előszámítás fordulónként (gyorsítás)
    press = {t: {rn: compute_pressure_factor(t, rn)
                 for rn in ("R32", "R16", "QF", "SF", "FINAL")} for t in remaining}

    def win_prob(a, b, rnd):
        ea = eff[a] * press[a][rnd] + TACTIC_MATRIX.get((tac[a], tac[b]), 0.0)
        eb = eff[b] * press[b][rnd] + TACTIC_MATRIX.get((tac[b], tac[a]), 0.0)
        return 1.0 / (1.0 + 10 ** (-(ea - eb) / 25.0))

    use_real_sf = set(remaining) == {x for p in SEMIFINAL_MATCHUPS.values()
                                     for x in (p["home"], p["away"])}

    rng = random.Random(seed)
    wins = defaultdict(int)
    finals = defaultdict(int)
    seeded = sorted(remaining, key=lambda t: -eff[t])

    for _ in range(n_sims):
        if use_real_sf:
            alive = []
            for p in SEMIFINAL_MATCHUPS.values():
                a, b = p["home"], p["away"]
                alive.append(a if rng.random() < win_prob(a, b, "SF") else b)
        else:
            alive = list(seeded)
            # kiegészítés erősorrendi "bye"-okkal 2-hatványra
            while len(alive) & (len(alive) - 1):
                alive.append(None)  # bye
            while len(alive) > 2:
                rnd = _bracket_round_name(len(alive))
                nxt = []
                half = len(alive) // 2
                for i in range(half):
                    a, b = alive[i], alive[len(alive) - 1 - i]
                    if b is None: nxt.append(a); continue
                    if a is None: nxt.append(b); continue
                    nxt.append(a if rng.random() < win_prob(a, b, rnd) else b)
                alive = nxt
        a, b = alive[0], alive[1]
        finals[a] += 1; finals[b] += 1
        w = a if rng.random() < win_prob(a, b, "FINAL") else b
        wins[w] += 1

    ranked = sorted(remaining, key=lambda t: (-wins[t], -finals[t], -eff[t]))
    top5 = [{"team": t, "win_prob": round(wins[t] / n_sims * 100, 1),
             "final_prob": round(finals[t] / n_sims * 100, 1)} for t in ranked[:5]]
    if return_full:
        full = {t: round(wins[t] / n_sims * 100, 1) for t in remaining}
        return top5, remaining, full
    return top5, remaining


# ==============================================================================
# MECCS-PREDIKCIÓ (as-of)
# ==============================================================================

def predict_final_chained(asof):
    """Döntő-predikció láncolva: valós eredmények végéig tényadat, onnan a
    modell saját elődöntő-predikcióiból építkezik."""
    res_ids = {r["match_id"]: r for r in asof}
    sides = []  # [(csapat -> döntőbe jutás valószínűsége), ...] a két ágra
    chain_notes = []
    for sf_id, p in SEMIFINAL_MATCHUPS.items():
        a, b = p["home"], p["away"]
        if sf_id in res_ids and res_ids[sf_id].get("winner"):
            w = res_ids[sf_id]["winner"]
            sides.append({w: 1.0})
            chain_notes.append({"match": f"{a} – {b}", "type": "valós eredmény",
                                "detail": f"{w} továbbjutott"})
        else:
            pa, _, pb = match_probability(a, b, "SF", asof, NEWS_MODS or None)
            sides.append({a: pa, b: pb})
            chain_notes.append({"match": f"{a} – {b}", "type": "modell-predikció",
                                "detail": f"{a} {pa*100:.0f}% – {pb*100:.0f}% {b}"})
    candidates = defaultdict(float)
    for t1, p1 in sides[0].items():
        for t2, p2 in sides[1].items():
            pw, _, pl = match_probability(t1, t2, "FINAL", asof, NEWS_MODS or None)
            candidates[t1] += p1 * p2 * pw
            candidates[t2] += p1 * p2 * pl
    ranked = sorted(candidates.items(), key=lambda x: -x[1])
    return {
        "chained": True,
        "chain": chain_notes,
        "candidates": [{"team": t, "win_prob": round(p * 100, 1)} for t, p in ranked],
        "predicted_outcome": ranked[0][0],
        "favorite_prob": round(ranked[0][1] * 100, 1),
    }


def get_match(match_id):
    for m in build_timeline():
        if m["match_id"] == match_id:
            return m
    raise HTTPException(404, f"Ismeretlen meccs: {match_id}")


_predict_cache = {}

def predict_match_core(m, asof):
    """Csak a meccs-szintű predikció (top5 nélkül) — a tömeges validáció is
    ezt használja, hogy gyors legyen."""
    if m["match_id"] == "FINAL" and (m["home"] is None or m["away"] is None):
        return predict_final_chained(asof)
    rn = round_name_for(m["round"])
    p_home, p_draw, p_away = match_probability(m["home"], m["away"], rn, asof, NEWS_MODS or None)
    outcomes = {m["home"]: p_home, "döntetlen": p_draw, m["away"]: p_away}
    best = max(outcomes.items(), key=lambda x: x[1])
    return {
        "chained": False,
        "p_home": round(p_home * 100, 1),
        "p_draw": round(p_draw * 100, 1),
        "p_away": round(p_away * 100, 1),
        "predicted_outcome": best[0],
        "favorite_prob": round(best[1] * 100, 1),
    }


def make_prediction(match_id):
    if match_id in _predict_cache:
        return _predict_cache[match_id]
    m = get_match(match_id)
    asof = asof_results(match_id)
    top5, remaining = asof_top5(asof)
    pred = predict_match_core(m, asof)

    # Csapat-bontások: normál meccsnél a két résztvevő, láncolt döntőnél a
    # két legesélyesebb jelölt
    if pred.get("chained"):
        c = [x["team"] for x in pred["candidates"][:2]]
        breakdowns = [team_breakdown(c[0], asof, "FINAL", c[1]),
                      team_breakdown(c[1], asof, "FINAL", c[0])]
        bd_note = "A döntő párosítása még nyitott — a két legesélyesebb jelölt bontása."
    else:
        breakdowns = [team_breakdown(m["home"], asof, m["round"], m["away"]),
                      team_breakdown(m["away"], asof, m["round"], m["home"])]
        bd_note = None

    score_pred = None
    if PARAM_MODE["engine"] == "poisson" and m.get("home") and m.get("away"):
        import predictor_wc2026 as P
        try:
            score_pred = P.score_prediction(m["home"], m["away"],
                                            round_name_for(m["round"]), asof)
        except Exception:
            score_pred = None

    payload = {
        "match": m,
        "engine": PARAM_MODE["engine"],
        "score_prediction": score_pred,
        "round_label": ROUND_LABELS.get(m["round"], str(m["round"])),
        "asof_matches_used": len(asof),
        "prediction": pred,
        "top5_at_moment": top5,
        "remaining_count": len(remaining),
        "breakdowns": breakdowns,
        "breakdown_note": bd_note,
    }
    _predict_cache[match_id] = payload
    log_prediction(match_id, m, pred)
    return payload


# ==============================================================================
# VALÓSÁG + KIÉRTÉKELÉS
# ==============================================================================

def actual_outcome_of(r):
    """Egy lejátszott meccs tényleges kimenetele a predikció nyelvén."""
    hg, ag = r.get("home_goals"), r.get("away_goals")
    if r.get("round") in (1, 2, 3) and hg == ag:
        return "döntetlen"
    return r.get("winner")


def brier_score(pred, actual, match):
    """Többkimenetelű Brier-pontszám (0 = tökéletes, alacsonyabb a jobb)."""
    if pred.get("chained"):
        probs = {c["team"]: c["win_prob"] / 100 for c in pred["candidates"]}
    else:
        probs = {match["home"]: pred["p_home"] / 100,
                 "döntetlen": pred["p_draw"] / 100,
                 match["away"]: pred["p_away"] / 100}
    score = 0.0
    for outcome, p in probs.items():
        o = 1.0 if outcome == actual else 0.0
        score += (p - o) ** 2
    return round(score, 4)


def evaluate_match(pred, r):
    """Predikció vs valóság: verdikt + Brier. A "szoros" küszöb fordulófüggő:
    csoportkörben (3 kimenetel) 40%, kiesésesben (2 kimenetel) 45%."""
    actual = actual_outcome_of(r)
    correct = (pred["predicted_outcome"] == actual)
    close_th = 40.0 if r.get("round") in (1, 2, 3) else 45.0
    verdict = "correct" if correct else ("close" if pred["favorite_prob"] < close_th else "wrong")
    return {
        "actual_outcome": actual,
        "score": f"{r.get('home_goals')}–{r.get('away_goals')}"
                 + (" (h.u.)" if r.get("extra_time") and not r.get("penalties") else "")
                 + (f" (tiz. {r.get('pen_home')}–{r.get('pen_away')})" if r.get("penalties") else ""),
        "home": r["home"], "away": r["away"],
        "extra_time": bool(r.get("extra_time")), "penalties": bool(r.get("penalties")),
        "source": r.get("source", "dataset"),
        "correct": correct, "verdict": verdict,
        "brier": brier_score(pred, actual, {"home": r["home"], "away": r["away"]}),
    }


def reveal(match_id):
    m = get_match(match_id)
    res = merged_results()
    if match_id not in res:
        return {"match_id": match_id, "played": False,
                "message": "Ezt a meccset még nem játszották le — itt csak a "
                           "modell láncolt predikciója él."}
    pred = make_prediction(match_id)["prediction"]
    entry = evaluate_match(pred, res[match_id])
    log_reveal(match_id, entry)
    return {"match_id": match_id, "played": True, **entry, "stats": running_stats()}


def build_baselines():
    """Naiv bázisvonalak UGYANAZON a 100 meccsen — ez adja meg, mihez képest
    jó vagy rossz a modell 71%-a. Enélkül a szám önmagában értelmezhetetlen."""
    import predictor_wc2026 as P
    res = merged_results()
    timeline = [m for m in build_timeline() if m["match_id"] in res]

    def outcome(r):
        return actual_outcome_of(r)

    rows = []

    # 1) Mindig a magasabb FIFA-pontszámú csapat nyer (determinisztikus)
    for label, key in [("Mindig a magasabb FIFA-pontszámú", "fifa_ranking_score"),
                       ("Mindig a nagyobb sztárértékű", "star_player_score")]:
        hits = 0
        for m in timeline:
            r = res[m["match_id"]]
            a, b = r["home"], r["away"]
            pick = a if TEAMS.get(a, {}).get(key, 0) >= TEAMS.get(b, {}).get(key, 0) else b
            if pick == outcome(r):
                hits += 1
        acc = hits / len(timeline)
        rows.append({"name": label, "accuracy": round(acc * 100, 1),
                     "brier": round(2 * (1 - acc), 3),
                     "note": "determinisztikus: nem tud esélyt mondani, "
                             "mindig 100%-ot állít"})

    # 2) Érmefeldobás (esélyek egyenletesen szétosztva)
    b_coin, hits = 0.0, 0
    rng = random.Random(11)
    for m in timeline:
        r = res[m["match_id"]]
        k = 3 if r["round"] in (1, 2, 3) else 2
        p = 1.0 / k
        b_coin += sum((p - (1.0 if i == 0 else 0.0)) ** 2 for i in range(k))
        if rng.random() < p:
            hits += 1
    rows.append({"name": "Érmefeldobás (egyenletes esélyek)",
                 "accuracy": round(hits / len(timeline) * 100, 1),
                 "brier": round(b_coin / len(timeline), 3),
                 "note": "referencia-alj"})

    # 3) Csupasz ELO: csak a súlyozott alapkomponensek, minden szorzó kikapcsolva
    saved = P.get_params()
    bare = dict(P.DEFAULT_PARAMS)
    bare.update({"mom_goal_diff": 0, "mom_loss": 0, "mom_win_streak": 0,
                 "mom_clean_sheet": 0, "mom_et_penalty": 0, "mom_pen_penalty": 0,
                 "tactic_scale": 0, "pressure_scale": 0, "context_scale": 0,
                 "form_level": 0, "form_trend": 0})
    P.set_params(bare)
    asof, hits, briers = [], 0, []
    for m in timeline:
        r = res[m["match_id"]]
        pred = predict_match_core(m, asof)
        ev = evaluate_match(pred, r)
        hits += 1 if ev["correct"] else 0
        briers.append(ev["brier"])
        asof.append(r)
    rows.append({"name": "Csupasz alapmodell (csak erő + ELO, szorzók nélkül)",
                 "accuracy": round(hits / len(timeline) * 100, 1),
                 "brier": round(sum(briers) / len(briers), 3),
                 "note": "a modell váza, minden finomság nélkül"})
    P.set_params(saved)

    # 4) A teljes modell az aktív súly-móddal
    full = validate_all(log=False)
    rows.append({"name": f"A modell ({'kalibrált' if PARAM_MODE['mode']=='calibrated' else 'eredeti'} súlyok)",
                 "accuracy": full["stats"]["accuracy"],
                 "brier": full["stats"]["avg_brier"],
                 "note": "as-of lánc, teljes tényezőkészlet", "is_model": True})

    # 5) Piaci konszenzus — CSAK valós adatból (market_odds.json). Kitalált
    #    számokkal nem helyettesítjük: az pont az a hiba lenne, amit a projekt
    #    elején a GPT-eredményeknél kigyomláltunk.
    market = load_json("market_odds.json", {})
    m_hits, m_briers = 0, []
    for m in timeline:
        odds = market.get(m["match_id"])
        if not odds:
            continue
        r = res[m["match_id"]]
        act = outcome(r)
        probs = {r["home"]: odds.get("home", 0.0), "döntetlen": odds.get("draw", 0.0),
                 r["away"]: odds.get("away", 0.0)}
        tot = sum(probs.values()) or 1.0
        probs = {k: v / tot for k, v in probs.items()}
        m_briers.append(sum((p - (1.0 if k == act else 0.0)) ** 2
                            for k, p in probs.items()))
        if max(probs, key=probs.get) == act:
            m_hits += 1
    market_note = None
    if m_briers:
        rows.append({"name": f"Piaci konszenzus ({len(m_briers)} meccs)",
                     "accuracy": round(m_hits / len(m_briers) * 100, 1),
                     "brier": round(sum(m_briers) / len(m_briers), 3),
                     "note": "a kemény mérce — a piac konszenzusa"})
    else:
        market_note = ('Piaci bázisvonal: NINCS ADAT. Ez lenne a legkeményebb mérce, '
                       'de historikus fogadóirodai esélyek nélkül nem számolható — '
                       'és kitalált számokkal nem helyettesítjük. Töltsd fel a '
                       'market_odds.json-t így, és a sor magától megjelenik: '
                       '{"A1": {"home": 0.55, "draw": 0.27, "away": 0.18}, ...}')

    rows.sort(key=lambda r: -(r["accuracy"] or 0))
    best_naive = max(r["accuracy"] for r in rows if not r.get("is_model"))
    model = next(r for r in rows if r.get("is_model"))
    for r in rows:
        r["bss"] = brier_skill_score(r["brier"])
    return {"n": len(timeline), "rows": rows, "market_note": market_note,
            "reference_brier": REFERENCE_BRIER,
            "verdict": (
                f"TALÁLATI ARÁNYBAN a modell ({model['accuracy']}%) NEM veri meg a "
                f"legjobb naiv szabályt ({best_naive}%) — ezt őszintén ki kell mondani. "
                "A modell értéke máshol van: a naiv szabály csak annyit tud mondani, "
                "hogy \"ez a csapat nyer\", 100%-os magabiztossággal, mindig. "
                "A modell viszont ESÉLYT mond, és tudja, mikor bizonytalan — ezért a "
                f"Brier-pontszáma {model['brier']} a naiv szabály "
                f"{max(r['brier'] for r in rows if not r.get('is_model') and r['brier'])}-"
                "es értékével szemben. Ha csak azt kérdezed, ki nyer: elég a FIFA-rangsor. "
                "Ha azt is, hogy mennyire biztos: kell a modell.")}


def validate_all(log=True):
    """Az ÖSSZES lejátszott meccs as-of predikciója + kiértékelése egyben.
    A top5-számítást kihagyja, ezért gyors."""
    res = merged_results()
    timeline = build_timeline()
    hist = load_json(HISTORY_FILE, {})
    items = []
    by_round = defaultdict(lambda: {"n": 0, "correct": 0, "close": 0, "wrong": 0, "brier": 0.0})
    asof = []
    now = datetime.now(timezone.utc).isoformat()

    for m in timeline:
        mid = m["match_id"]
        if mid not in res:
            continue
        pred = predict_match_core(m, asof)
        entry = evaluate_match(pred, res[mid])
        rl = "Csoportkör" if m["round"] in (1, 2, 3) else str(m["round"])
        b = by_round[rl]
        b["n"] += 1; b[entry["verdict"]] += 1; b["brier"] += entry["brier"]
        items.append({"match_id": mid, "verdict": entry["verdict"],
                      "home": m["home"], "away": m["away"], "score": entry["score"],
                      "predicted": pred["predicted_outcome"],
                      "favorite_prob": pred["favorite_prob"], "brier": entry["brier"]})
        h = hist.get(mid, {"match_id": mid})
        h.update({"date": m["date"], "round": str(m["round"]),
                  "predicted_outcome": pred["predicted_outcome"],
                  "favorite_prob": pred["favorite_prob"],
                  "actual_outcome": entry["actual_outcome"],
                  "correct": entry["correct"], "verdict": entry["verdict"],
                  "brier": entry["brier"], "mode": PARAM_MODE["mode"],
                  "engine": PARAM_MODE["engine"],
                  "predicted_at": now, "revealed_at": now})
        hist[mid] = h
        asof.append(res[mid])  # a lánc a következő meccshez már ismeri ezt

    if log:
        save_json(hist, HISTORY_FILE)
    rounds = []
    for rl in ["Csoportkör", "R32", "R16", "QF", "SF", "FINAL"]:
        if rl in by_round:
            b = by_round[rl]
            rounds.append({"round": rl, "n": b["n"], "correct": b["correct"],
                           "close": b["close"], "wrong": b["wrong"],
                           "accuracy": round(b["correct"] / b["n"] * 100, 1),
                           "avg_brier": round(b["brier"] / b["n"], 3)})
    if log:
        stats = running_stats()
    else:
        corr = sum(1 for i in items if i["verdict"] == "correct")
        ab = round(sum(i["brier"] for i in items) / len(items), 3)
        stats = {"checked": len(items), "correct": corr,
                 "accuracy": round(corr / len(items) * 100, 1),
                 "avg_brier": ab, "bss": brier_skill_score(ab)}
    return {"items": items, "by_round": rounds, "stats": stats}


# ==============================================================================
# PREDIKCIÓ-NAPLÓ + FUTÓ STATISZTIKA
# ==============================================================================

def log_prediction(match_id, m, pred):
    hist = load_json(HISTORY_FILE, {})
    e = hist.get(match_id, {})
    e.update({"match_id": match_id, "date": m["date"], "round": str(m["round"]),
              "predicted_outcome": pred["predicted_outcome"],
              "favorite_prob": pred["favorite_prob"],
              "mode": PARAM_MODE["mode"], "engine": PARAM_MODE["engine"],
              "predicted_at": datetime.now(timezone.utc).isoformat()})
    hist[match_id] = e
    save_json(hist, HISTORY_FILE)


def log_reveal(match_id, entry):
    hist = load_json(HISTORY_FILE, {})
    e = hist.get(match_id, {"match_id": match_id})
    e.update({"actual_outcome": entry["actual_outcome"], "correct": entry["correct"],
              "verdict": entry["verdict"], "brier": entry["brier"],
              "mode": PARAM_MODE["mode"], "engine": PARAM_MODE["engine"],
              "revealed_at": datetime.now(timezone.utc).isoformat()})
    hist[match_id] = e
    save_json(hist, HISTORY_FILE)


def running_stats():
    """Csak az AKTÍV súly-móddal készült bejegyzéseket számolja — különben az
    eredeti és kalibrált eredmények összekeverednének."""
    hist = load_json(HISTORY_FILE, {})
    revealed = [e for e in hist.values() if "correct" in e
                and e.get("mode", "default") == PARAM_MODE["mode"]
                and e.get("engine", "elo") == PARAM_MODE["engine"]]
    if not revealed:
        return {"checked": 0, "correct": 0, "accuracy": None, "avg_brier": None}
    correct = sum(1 for e in revealed if e["correct"])
    briers = [e["brier"] for e in revealed if e.get("brier") is not None]
    avg_b = round(sum(briers) / len(briers), 3) if briers else None
    return {"checked": len(revealed), "correct": correct,
            "accuracy": round(correct / len(revealed) * 100, 1),
            "avg_brier": avg_b,
            "bss": brier_skill_score(avg_b)}


# Referencia-Brier: a naiv "mindig a magasabb FIFA-pontszámú nyer" szabály,
# ami 100%-os magabiztossággal állít -> Brier = 2*(1-találat) = 0.560.
# Ez a projekt saját tanulságának beépítése: nem az abszolút százalék
# számít, hanem hogy mennyivel jobb a modell a naiv szabálynál.
REFERENCE_BRIER = 0.560


def brier_skill_score(model_brier):
    """BSS = 1 - Brier_modell / Brier_referencia.
    +1 = tökéletes, 0 = ugyanolyan jó, mint a naiv szabály, < 0 = rosszabb."""
    if not model_brier:
        return None
    return round(1.0 - model_brier / REFERENCE_BRIER, 3)


# ==============================================================================
# TOP5 IDŐVONAL (grafikonhoz) — háttérszámítás, cache-elve
# ==============================================================================

PARAM_MODE = {"mode": "default", "engine": "elo"}  # mode: default|calibrated; engine: elo|poisson
_calib_state = {"status": "idle", "progress": 0, "total": 0}


def apply_param_mode():
    """Az aktív motor + súly-mód érvényesítése, predikció-cache ürítés."""
    import predictor_wc2026 as P
    eng = PARAM_MODE["engine"]
    P.set_engine(eng)
    if PARAM_MODE["mode"] == "calibrated":
        import calibration
        rep = calibration.load_report(eng)
        if rep:
            P.set_params(rep["params"])
        else:
            PARAM_MODE["mode"] = "default"
            P.set_params(P.DEFAULT_PARAMS)
    else:
        P.set_params(P.DEFAULT_PARAMS)
    _predict_cache.clear()


def _run_calibration():
    try:
        import calibration
        def cb(i, n):
            _calib_state["progress"] = i
            _calib_state["total"] = n
        calibration.calibrate(progress_cb=cb, engine=PARAM_MODE["engine"])
        _calib_state["status"] = "done"
    except Exception as e:
        _calib_state["status"] = "error"
        _calib_state["error"] = str(e)
    finally:
        apply_param_mode()   # a kalibráció közben átírt globálok visszaállítása


TIMELINE_CACHE_FILE = "top5_timeline.json"
_tl_state = {"status": "idle", "progress": 0, "total": 0}
_tl_lock = threading.Lock()


def _compute_timeline():
    try:
        res = merged_results()
        timeline = build_timeline()
        _tl_state["total"] = len(timeline)
        points, asof = [], []
        for i, m in enumerate(timeline):
            top5, remaining, full = asof_top5(asof, n_sims=800, seed=42,
                                              return_full=True)
            points.append({"idx": i, "match_id": m["match_id"], "date": m["date"],
                           "round": str(m["round"]),
                           "label": (f"{m['home']} – {m['away']}"
                                     if m["home"] and m["away"] else "Döntő"),
                           "played": m["match_id"] in res,
                           "remaining": len(remaining),
                           "top5": top5, "probs": full})
            if m["match_id"] in res:
                asof.append(res[m["match_id"]])
            _tl_state["progress"] = i + 1
        # + záró pont: minden ismert eredmény UTÁN (mai állapot)
        top5, remaining, full = asof_top5(asof, n_sims=800, seed=42, return_full=True)
        points.append({"idx": len(timeline), "match_id": "_NOW",
                       "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                       "round": "most", "label": "Aktuális állapot", "played": False,
                       "remaining": len(remaining), "top5": top5, "probs": full})
        # Vonalat csak az kap, aki valaha top5-ben volt
        charted = []
        for p in points:
            for t in p["top5"]:
                if t["team"] not in charted:
                    charted.append(t["team"])
        save_json({"computed_at": datetime.now(timezone.utc).isoformat(),
                   "charted_teams": charted, "points": points},
                  TIMELINE_CACHE_FILE)
        _tl_state["status"] = "done"
    except Exception as e:
        _tl_state["status"] = "error"
        _tl_state["error"] = str(e)


# ==============================================================================
# ELEMZÉS: sztár vs. kollektíva vs. edző — a VALÓS eredmények alapján
# ==============================================================================

ROUND_RANK = {"group": 0, "R32": 1, "R16": 2, "QF": 3, "SF": 4, "FINAL": 5}
RANK_LABEL = {0: "Csoportkör", 1: "R32", 2: "R16", 3: "Negyeddöntő",
              4: "Elődöntős", 5: "Döntős"}


def achieved_ranks():
    """Minden csapat legmesszebbi VALÓS köre (merged eredményekből, nem a
    statikus eliminated_round mezőből)."""
    res = merged_results()
    rank = {t: 0 for t in TEAMS}
    for r in res.values():
        rr = ROUND_RANK.get(r.get("round"))
        if rr:
            for side in (r.get("home"), r.get("away")):
                if side in rank:
                    rank[side] = max(rank[side], rr)
    for p in SEMIFINAL_MATCHUPS.values():  # elődöntősök akkor is, ha még nem játszottak
        for side in (p["home"], p["away"]):
            if side in rank:
                rank[side] = max(rank[side], ROUND_RANK["SF"])
    return rank


def _percentile(values, pct):
    s = sorted(values)
    k = (len(s) - 1) * pct / 100.0
    f = int(k)
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


def _spearman(xs, ys):
    """Spearman rangkorreláció, külső könyvtár nélkül (kötések átlagrangja)."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def build_analysis():
    ranks = achieved_ranks()
    teams = list(TEAMS.keys())
    star = {t: TEAMS[t].get("star_player_score", 50) for t in teams}
    depth = {t: TEAMS[t].get("squad_depth", 50) for t in teams}
    coach = {t: TEAMS[t].get("coach_quality", 50) for t in teams}
    fifa = {t: TEAMS[t].get("fifa_ranking_score", 50) for t in teams}

    star_hi = _percentile(list(star.values()), 67)
    depth_hi = _percentile(list(depth.values()), 67)

    def archetype(t):
        s_hi, d_hi = star[t] >= star_hi, depth[t] >= depth_hi
        if s_hi and d_hi: return "Sztár + mélység"
        if s_hi: return "Sztárcentrikus"
        if d_hi: return "Kollektíva"
        return "Átlagos"

    arch = defaultdict(list)
    for t in teams:
        arch[archetype(t)].append(t)
    arch_rows = []
    for name in ["Sztár + mélység", "Sztárcentrikus", "Kollektíva", "Átlagos"]:
        ts = arch.get(name, [])
        if not ts: continue
        rs = [ranks[t] for t in ts]
        r16plus = sum(1 for r in rs if r >= 2)
        best = max(ts, key=lambda t: (ranks[t], star[t]))
        # Wilson-szerű durva hibahatár az R16+ arányra (kis n!)
        p = r16plus / len(ts)
        se = (p * (1 - p) / len(ts)) ** 0.5 * 100
        arch_rows.append({
            "archetype": name, "n": len(ts),
            "r16_plus_se": round(1.96 * se, 0),
            "avg_rank": round(sum(rs) / len(rs), 2),
            "avg_rank_label": RANK_LABEL[min(5, round(sum(rs) / len(rs)))],
            "r16_plus_pct": round(r16plus / len(ts) * 100, 0),
            "best": f"{best} ({RANK_LABEL[ranks[best]]})",
            "teams_sf": [t for t in ts if ranks[t] >= 4],
        })

    def _rho_ci(vals, n_boot=800, seed=5):
        """Bootstrap CI a rangkorrelációra — 48 csapat kevés, a bizonytalanság
        érdemi, ezt ki kell mondani."""
        rng = random.Random(seed)
        out = []
        for _ in range(n_boot):
            samp = [rng.choice(teams) for _ in teams]
            out.append(_spearman([vals[t] for t in samp], [ranks[t] for t in samp]))
        out.sort()
        return [round(out[int(0.025 * n_boot)], 2), round(out[int(0.975 * n_boot)], 2)]

    corr = [{"factor": lbl,
             "rho": round(_spearman([v[t] for t in teams], [ranks[t] for t in teams]), 3),
             "ci": _rho_ci(v)}
            for lbl, v in [("FIFA rangsor", fifa), ("Sztárjátékos", star),
                           ("Keretmélység", depth), ("Edzőminőség", coach)]]
    corr.sort(key=lambda c: -c["rho"])

    # Konfliktus-meccsek: ahol a két tényező ELLENTÉTES irányba mutatott
    THRESH = 5
    res = merged_results()
    def conflict(fa, fb, la, lb):
        n = a_wins = 0
        for r in res.values():
            w = r.get("winner")
            h, aw = r.get("home"), r.get("away")
            if not w or h not in TEAMS or aw not in TEAMS: continue
            da = fa[h] - fa[aw]
            db = fb[h] - fb[aw]
            if abs(da) < THRESH or abs(db) < THRESH or da * db >= 0: continue
            n += 1
            adv_a_side = h if da > 0 else aw   # az fa-előnyös csapat
            if w == adv_a_side: a_wins += 1
        return {"label": f"{la}-előny vs {lb}-előny", "n": n,
                "a_label": la, "a_wins": a_wins, "b_label": lb,
                "b_wins": n - a_wins,
                "a_pct": round(a_wins / n * 100, 0) if n else None}

    conflicts = [conflict(star, depth, "Sztár", "Mélység"),
                 conflict(coach, star, "Edző", "Sztár"),
                 conflict(coach, depth, "Edző", "Mélység")]

    # ── Profil-dőlés + túlteljesítés (FIFA-szinthez mérve) ──
    # Mivel a négy tényező az adatbázisban szinte együtt mozog (ρ≈0.99), a
    # tisztességes kérdés: AZONOS FIFA-szint mellett a sztár-dőlés vagy a
    # kollektív-dőlés járt-e messzebbre jutással?
    tilt = {t: star[t] - depth[t] for t in teams}   # + = sztár-túlsúly
    fifa_sorted = sorted(teams, key=lambda t: -fifa[t])
    quartile = {}
    q = len(teams) // 4
    for i, t in enumerate(fifa_sorted):
        quartile[t] = min(3, i // max(1, q))
    overperf = {}
    for t in teams:
        peers = [x for x in teams if quartile[x] == quartile[t] and x != t]
        exp = sum(ranks[x] for x in peers) / len(peers) if peers else 0
        overperf[t] = round(ranks[t] - exp, 2)
    tilt_over_rho = round(_spearman([tilt[t] for t in teams],
                                    [overperf[t] for t in teams]), 3)
    def tilt_label(v):
        return "sztár-dőlés" if v >= 4 else ("kollektív-dőlés" if v <= -4 else "kiegyensúlyozott")
    perf_sorted = sorted(teams, key=lambda t: -overperf[t])
    def perf_row(t):
        return {"team": t, "tilt": tilt[t], "tilt_label": tilt_label(tilt[t]),
                "overperf": overperf[t], "achieved": RANK_LABEL[ranks[t]],
                "fifa": fifa[t]}
    tilt_analysis = {
        "rho_tilt_overperf": tilt_over_rho,
        "collinearity_note": "A sztár/mélység/edző pontszámok az adatbázisban "
                             "szinte együtt mozognak (Spearman ρ≈0.99), ezért "
                             "önálló hatásuk közvetlenül nem szétválasztható — "
                             "az alábbi dőlés-elemzés a kivételekre épít.",
        "overperformers": [perf_row(t) for t in perf_sorted[:5]],
        "underperformers": [perf_row(t) for t in perf_sorted[-5:]][::-1],
        "notable": [perf_row(t) for t in sorted(teams, key=lambda x: -abs(tilt[x]))[:6]],
    }

    scatter = [{"team": t, "star": star[t], "depth": depth[t], "coach": coach[t],
                "rank": ranks[t], "rank_label": RANK_LABEL[ranks[t]],
                "archetype": archetype(t)} for t in teams]

    return {"thresholds": {"star": round(star_hi, 1), "depth": round(depth_hi, 1)},
            "archetypes": arch_rows, "correlations": corr,
            "conflicts": conflicts, "tilt_analysis": tilt_analysis,
            "scatter": scatter,
            "note": "Egyetlen torna, 48 csapat — összefüggés, nem bizonyíték. "
                    "Egy-két meglepetés (pl. Brazil–Norway) érdemben mozgatja a számokat."}


# ==============================================================================
# API VÉGPONTOK
# ==============================================================================

@app.get("/api/matches")
def api_matches():
    hist = load_json(HISTORY_FILE, {})
    tl = build_timeline()
    for m in tl:
        h = hist.get(m["match_id"], {})
        m["verdict"] = h.get("verdict") if (
            h.get("mode", "default") == PARAM_MODE["mode"]
            and h.get("engine", "elo") == PARAM_MODE["engine"]) else None
        m["round_label"] = ROUND_LABELS.get(m["round"], str(m["round"]))
    return JSONResponse({"build": KV_BUILD, "matches": tl, "stats": running_stats(),
                         "param_mode": PARAM_MODE["mode"],
                         "engine": PARAM_MODE["engine"],
                         "has_calibration": os.path.exists(
                             __import__("calibration").calib_file(PARAM_MODE["engine"]))},
                        headers={"Cache-Control": "no-store"})


@app.get("/api/predict/{match_id}")
def api_predict(match_id: str):
    return JSONResponse(make_prediction(match_id),
                        headers={"Cache-Control": "no-store"})


@app.get("/api/reveal/{match_id}")
def api_reveal(match_id: str):
    return JSONResponse(reveal(match_id), headers={"Cache-Control": "no-store"})


@app.get("/api/refresh-data")
def api_refresh_data():
    """Egygombos frissítés: hivatalos letöltés (ha van API-kulcs) -> verify
    -> sync -> cache-érvénytelenítés."""
    import official_data
    log = []
    fetched = official_data.fetch_official()
    log.append("Hivatalos letöltés: " + ("OK" if fetched else
               "kihagyva (nincs API-kulcs vagy nincs hálózat) — a meglévő cache-ből ellenőrzök"))
    mismatches = official_data.verify(quiet=True)
    if mismatches is None:
        log.append("Nincs hivatalos cache — ellenőrzés kihagyva.")
    elif mismatches:
        official_data.sync()
        log.append(f"{len(mismatches)} eltérés javítva a hivatalos adat szerint.")
    else:
        log.append("Minden ellenőrizhető meccs egyezik a hivatalossal.")
    _predict_cache.clear()
    if os.path.exists(TIMELINE_CACHE_FILE):
        os.remove(TIMELINE_CACHE_FILE)
    _tl_state.update({"status": "idle", "progress": 0, "total": 0})
    log.append("Predikció-cache és top5-idővonal érvénytelenítve.")
    return JSONResponse({"log": log, "stats": running_stats()},
                        headers={"Cache-Control": "no-store"})


@app.get("/api/calibrate")
def api_calibrate():
    with _tl_lock:
        if _calib_state["status"] == "running":
            return JSONResponse({"status": "running",
                                 "progress": _calib_state["progress"],
                                 "total": _calib_state["total"]})
        import calibration as _cal
        _cf = _cal.calib_file(PARAM_MODE["engine"])
        if _calib_state["status"] == "done" or (
                _calib_state["status"] == "idle" and os.path.exists(_cf)):
            import calibration
            _calib_state["status"] = "done"
            return JSONResponse({"status": "done",
                                 "report": calibration.load_report(PARAM_MODE["engine"]),
                                 "mode": PARAM_MODE["mode"]},
                                headers={"Cache-Control": "no-store"})
        _calib_state.update({"status": "running", "progress": 0, "total": 0})
        threading.Thread(target=_run_calibration, daemon=True).start()
    return JSONResponse({"status": "running", "progress": 0, "total": 0})


@app.get("/api/calibrate/rerun")
def api_calibrate_rerun():
    with _tl_lock:
        if _calib_state["status"] == "running":
            return JSONResponse({"status": "running"})
        import calibration as _cal
        _cf = _cal.calib_file(PARAM_MODE["engine"])
        if os.path.exists(_cf):
            os.remove(_cf)
        _calib_state.update({"status": "running", "progress": 0, "total": 0})
        threading.Thread(target=_run_calibration, daemon=True).start()
    return JSONResponse({"status": "running"})


@app.get("/api/params/mode/{mode}")
def api_param_mode(mode: str):
    if mode not in ("default", "calibrated"):
        raise HTTPException(400, "mode: default | calibrated")
    import calibration as _cal
    if mode == "calibrated" and not os.path.exists(_cal.calib_file(PARAM_MODE["engine"])):
        raise HTTPException(409, "Ehhez a motorhoz még nincs kalibráció — futtasd előbb.")
    PARAM_MODE["mode"] = mode
    apply_param_mode()
    # A top5-idővonal is más motorral számolna — érvénytelenítjük
    if os.path.exists(TIMELINE_CACHE_FILE):
        os.remove(TIMELINE_CACHE_FILE)
    _tl_state.update({"status": "idle", "progress": 0, "total": 0})
    return JSONResponse({"mode": mode, "stats_note": "predikció-cache ürítve"},
                        headers={"Cache-Control": "no-store"})


@app.get("/api/engine/{engine}")
def api_engine(engine: str):
    if engine not in ("elo", "poisson"):
        raise HTTPException(400, "engine: elo | poisson")
    import calibration as _cal
    PARAM_MODE["engine"] = engine
    if not os.path.exists(_cal.calib_file(engine)):
        PARAM_MODE["mode"] = "default"
    apply_param_mode()
    _calib_state.update({"status": "idle", "progress": 0, "total": 0})
    if os.path.exists(TIMELINE_CACHE_FILE):
        os.remove(TIMELINE_CACHE_FILE)
    _tl_state.update({"status": "idle", "progress": 0, "total": 0})
    return JSONResponse({"engine": engine, "mode": PARAM_MODE["mode"],
                         "has_calibration": os.path.exists(_cal.calib_file(engine))},
                        headers={"Cache-Control": "no-store"})


@app.get("/api/baselines")
def api_baselines():
    return JSONResponse(build_baselines(), headers={"Cache-Control": "no-store"})


@app.get("/api/analysis")
def api_analysis():
    return JSONResponse(build_analysis(), headers={"Cache-Control": "no-store"})


@app.get("/api/validate-all")
def api_validate_all():
    return JSONResponse(validate_all(), headers={"Cache-Control": "no-store"})


@app.get("/api/top5-timeline")
def api_top5_timeline():
    with _tl_lock:
        if _tl_state["status"] == "done" or (
                _tl_state["status"] == "idle" and os.path.exists(TIMELINE_CACHE_FILE)):
            _tl_state["status"] = "done"
            data = load_json(TIMELINE_CACHE_FILE, {})
            return JSONResponse({"status": "done", **data},
                                headers={"Cache-Control": "no-store"})
        if _tl_state["status"] == "idle":
            _tl_state.update({"status": "running", "progress": 0})
            threading.Thread(target=_compute_timeline, daemon=True).start()
        return JSONResponse({"status": _tl_state["status"],
                             "progress": _tl_state["progress"],
                             "total": _tl_state["total"],
                             "error": _tl_state.get("error")},
                            headers={"Cache-Control": "no-store"})


@app.get("/api/top5-timeline/recompute")
def api_top5_timeline_recompute():
    """Cache eldobása és újraszámítás (pl. új eredmény érkezése után)."""
    with _tl_lock:
        if _tl_state["status"] == "running":
            return JSONResponse({"status": "running",
                                 "progress": _tl_state["progress"],
                                 "total": _tl_state["total"]})
        if os.path.exists(TIMELINE_CACHE_FILE):
            os.remove(TIMELINE_CACHE_FILE)
        _tl_state.update({"status": "running", "progress": 0})
        threading.Thread(target=_compute_timeline, daemon=True).start()
    return JSONResponse({"status": "running", "progress": 0})


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(INDEX_HTML, headers={"Cache-Control": "no-store"})


INDEX_HTML = ""  # a frontend.html tartalma töltődik be indításkor

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8026)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "frontend_wc2026.html"), encoding="utf-8") as f:
        INDEX_HTML = f.read()
    print(f"  [{KV_BUILD}] Indítás: http://localhost:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
else:
    _fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend_wc2026.html")
    if os.path.exists(_fp):
        with open(_fp, encoding="utf-8") as f:
            INDEX_HTML = f.read()

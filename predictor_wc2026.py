"""
FIFA World Cup 2026 - Predikciós Motor
=======================================
ELO-alapú valószínűség-számítás + Monte Carlo szimuláció
+ GPT-frissített csapaterők + kontextuális tényezők

Modell tényezők:
  1. FIFA rangsor alappontszám (alap erő)
  2. Keretmélység és sztárjátékos minőség
  3. Edzőminőség
  4. Torna-momentum (eddigi meccsek alapján)
  5. Sérülések / felfüggesztések (GPT-frissítve)
  6. Fáradtság (meccsek száma, hosszabbítások)
  7. Taktikai stílus ütközés
  8. Konföderáció / utazás
  9. Hőség / helyszín hatás
 10. Nyomás / elvárások
 11. Torna-tapasztalat
"""

import math
import random
import json
import os
from collections import defaultdict
from data_wc2026 import (
    TEAMS, GROUP_STAGE_RESULTS, KNOCKOUT_RESULTS,
    CONTEXTUAL_FACTORS, MOMENTUM_WEIGHTS,
    SEMIFINAL_MATCHUPS, get_all_known_results
)

# ==============================================================================
# ALAP CSAPATERŐ SZÁMÍTÁS
# ==============================================================================

# ==============================================================================
# KALIBRÁLHATÓ PARAMÉTEREK
# Alapértékek = az eredeti beégetett konstansok (viselkedés változatlan).
# A kalibráció (calibration.py) ezeket állítja; set_params() cseréli le őket.
# ==============================================================================

DEFAULT_PARAMS = {
    "w_fifa": 0.35, "w_star": 0.20, "w_depth": 0.15, "w_coach": 0.10,
    "elo_divisor": 25.0,
    "draw_base": 0.28,
    "mom_goal_diff": 0.04,
    "mom_loss": -0.05,
    "mom_win_streak": 0.15,
    "mom_clean_sheet": 0.10,
    "mom_et_penalty": -0.08,
    "mom_pen_penalty": -0.05,
    "tactic_scale": 1.0,
    "pressure_scale": 0.1,
    "context_scale": 1.0,   # utazás/tapasztalat/hőség eltérése 1.0-tól skálázva
    # Fejlődési görbe (ellenfél-erővel korrigált gól-reziduál) — alapérték 0:
    # amíg a kalibráció nem igazolja a hasznát, nem változtat semmit
    "form_level": 0.0,      # a reziduál-SZINT hatása (jobban játszik, mint várták)
    "form_trend": 0.0,      # a reziduál-TREND hatása (meccsre meccsre fejlődik)
    # Poisson-gólmodell paraméterei (csak ENGINE="poisson" esetén élnek)
    "poisson_base_goals": 1.30,   # átlagos gólszám/csapat egyenlő felek között
    "poisson_strength": 0.030,    # erőkülönbség -> gólvárakozás átváltás
    "poisson_max_goals": 8,       # az eloszlás levágása
    "poisson_et_scale": 0.35,     # hosszabbítás: 30 perc a 90-hez képest
    "poisson_pen_edge": 0.15,     # tizenegyeseknél az erő súlya (0 = tiszta 50/50)
}

PARAM_BOUNDS = {
    "w_fifa": (0.10, 0.60), "w_star": (0.02, 0.45), "w_depth": (0.02, 0.40),
    "w_coach": (0.0, 0.30),
    "elo_divisor": (8.0, 60.0),
    "draw_base": (0.12, 0.40),
    "mom_goal_diff": (0.0, 0.10),
    "mom_loss": (-0.15, 0.0),
    "mom_win_streak": (0.0, 0.30),
    "mom_clean_sheet": (0.0, 0.20),
    "mom_et_penalty": (-0.20, 0.0),
    "mom_pen_penalty": (-0.15, 0.0),
    "tactic_scale": (0.0, 2.5),
    "pressure_scale": (0.0, 0.30),
    "context_scale": (0.0, 2.0),
    "form_level": (0.0, 0.08),
    "form_trend": (0.0, 0.10),
    "poisson_base_goals": (0.80, 2.20),
    "poisson_strength": (0.005, 0.080),
    "poisson_max_goals": (8, 8),      # fix, nem kalibrálandó
    "poisson_et_scale": (0.20, 0.60),
    "poisson_pen_edge": (0.0, 0.50),
}

PARAMS = dict(DEFAULT_PARAMS)

# Aktív valószínűség-motor: "elo" (eredeti) vagy "poisson" (gólmodell)
ENGINE = "elo"


def set_engine(name):
    """Motorválasztás: 'elo' | 'poisson'."""
    global ENGINE
    if name not in ("elo", "poisson"):
        raise ValueError("engine: elo | poisson")
    ENGINE = name


def get_engine():
    return ENGINE


def set_params(p):
    """Paraméter-vektor cseréje (hiányzó kulcsok alapértéken maradnak)."""
    global PARAMS
    PARAMS = dict(DEFAULT_PARAMS)
    PARAMS.update({k: v for k, v in p.items() if k in DEFAULT_PARAMS})


def get_params():
    return dict(PARAMS)


def _ctx(mult):
    """Kontextus-szorzó (utazás/tapasztalat/hőség) skálázása: az 1.0-tól
    való eltérést nyújtja/zsugorítja a context_scale."""
    return 1.0 + (mult - 1.0) * PARAMS["context_scale"]


TACTIC_MATRIX = {
    # (támadó stílus, védő stílus): módosító a támadónak
    ("high_press", "defensive"):   +3.0,
    ("possession",  "counter"):    +2.0,
    ("counter",     "possession"): +4.0,
    ("counter",     "high_press"): +2.5,
    ("high_press",  "possession"): +1.5,
    ("possession",  "high_press"): +1.0,
    ("defensive",   "counter"):    -2.0,
    ("defensive",   "possession"): -1.5,
}


def compute_base_strength(team_name, gpt_modifiers=None):
    """
    Kiszámolja egy csapat alap erő-indexét (0-100 skálán).
    
    Súlyok:
      - FIFA rangsor:        35%
      - Keretmélység:        15%
      - Sztárjátékos:        20%
      - Edzőminőség:         10%
      - Fáradtság:           10% (szorzó)
      - Sérülés:             10% (szorzó)
    """
    if team_name not in TEAMS:
        return 50.0

    t = TEAMS[team_name]
    base = (
        t["fifa_ranking_score"] * PARAMS["w_fifa"] +
        t["squad_depth"]        * PARAMS["w_depth"] +
        t["star_player_score"]  * PARAMS["w_star"] +
        t["coach_quality"]      * PARAMS["w_coach"]
    )
    # Szorzók
    base *= t.get("fatigue_factor", 1.0)
    base *= t.get("injury_factor", 1.0)

    # GPT módosítók (sérülések, hírek alapján)
    if gpt_modifiers and team_name in gpt_modifiers:
        base += gpt_modifiers[team_name]

    # Konföderációs utazás hatás
    conf = t.get("confederation", "UEFA")
    travel = CONTEXTUAL_FACTORS["travel_impact"].get(conf, 0.95)
    base *= _ctx(travel)

    # Torna-tapasztalat
    exp = CONTEXTUAL_FACTORS["tournament_experience"].get(
        team_name,
        CONTEXTUAL_FACTORS["tournament_experience"]["default"]
    )
    base *= _ctx(exp)

    # Hőség hatás
    heat = CONTEXTUAL_FACTORS["heat_impact"].get(conf, 0.97)
    base *= _ctx(heat)

    return max(10.0, min(100.0, base))


def compute_momentum(team_name, results_so_far):
    """
    Kiszámolja a csapat momentum-szorzóját az eddigi meccsek alapján.
    
    Figyelembe veszi:
    - Győzelmek/vereségek sorozata
    - Tiszta lapok
    - Hosszabbítások / büntetők (fáradtság)
    - Gólkülönbség
    """
    momentum = 1.0
    team_results = []

    for r in results_so_far:
        if r.get("home") == team_name or r.get("away") == team_name:
            team_results.append(r)

    if not team_results:
        return momentum

    win_streak = 0
    last_results = team_results[-3:]  # Utolsó 3 meccs

    for r in last_results:
        winner = r.get("winner")
        is_home = r.get("home") == team_name
        home_g = r.get("home_goals", 0)
        away_g = r.get("away_goals", 0)

        if winner == team_name:
            win_streak += 1
            goal_diff = (home_g - away_g) if is_home else (away_g - home_g)
            momentum += PARAMS["mom_goal_diff"] * min(goal_diff, 3)
        elif winner and winner != team_name:
            win_streak = 0
            momentum += PARAMS["mom_loss"]

        if r.get("extra_time"):
            momentum += PARAMS["mom_et_penalty"]
        if r.get("penalties"):
            momentum += PARAMS["mom_pen_penalty"]

        # Tiszta lap bónusz
        if is_home and away_g == 0:
            momentum += PARAMS["mom_clean_sheet"]
        elif not is_home and home_g == 0:
            momentum += PARAMS["mom_clean_sheet"]

    if win_streak >= 3:
        momentum += PARAMS["mom_win_streak"]
    elif win_streak >= 2:
        momentum += PARAMS["mom_win_streak"] * 0.5

    return max(0.6, min(1.4, momentum))


def compute_pressure_factor(team_name, round_name):
    """
    Nyomás/elvárás faktor - minél nagyobb a nyomás, annál több a kockázat.
    Kiemelten fontos a döntőhöz közeledve.
    """
    t = TEAMS.get(team_name, {})
    pressure = t.get("pressure_index", 50) / 100.0

    round_multipliers = {
        "group": 0.5,
        "R32": 0.7,
        "R16": 0.85,
        "QF": 1.0,
        "SF": 1.15,
        "FINAL": 1.3,
    }
    round_mult = round_multipliers.get(round_name, 1.0)

    # Magas nyomás = enyhe negatív hatás (túlzott elvárások)
    if pressure > 0.75:
        return 1.0 - (pressure - 0.75) * PARAMS["pressure_scale"] * round_mult
    return 1.0


def _static_strength(team_name):
    """Gyors, szorzók nélküli erő a forma-elváráshoz."""
    t = TEAMS.get(team_name)
    if not t:
        return 50.0
    return (t["fifa_ranking_score"] * PARAMS["w_fifa"] +
            t["squad_depth"] * PARAMS["w_depth"] +
            t["star_player_score"] * PARAMS["w_star"] +
            t["coach_quality"] * PARAMS["w_coach"])


def compute_form(team_name, results_so_far, with_details=False):
    """
    Fejlődési görbe: a csapat eddigi meccsein az ELLENFÉL EREJÉVEL korrigált
    gól-reziduál (tényleges gólkülönbség mínusz a papírforma szerint várt).
    Két jellemző: SZINT (exponenciálisan súlyozott átlag, a frissebb számít
    jobban) és TREND (legkisebb négyzetes meredekség = fejlődik/romlik).
    Bővítési pont: ha az eredmény-rekordokban lesz lap/csere adat
    (yellow_cards, red_cards, subs), a reziduál kiegészíthető velük.
    """
    series = []
    s_t = _static_strength(team_name)
    for r in results_so_far:
        is_home = r.get("home") == team_name
        if not is_home and r.get("away") != team_name:
            continue
        opp = r.get("away") if is_home else r.get("home")
        margin = ((r.get("home_goals", 0) or 0) - (r.get("away_goals", 0) or 0))
        if not is_home:
            margin = -margin
        exp_margin = (s_t - _static_strength(opp)) / 15.0
        resid = max(-3.0, min(3.0, margin - exp_margin))
        series.append({"opp": opp, "residual": round(resid, 2)})

    if not series:
        level = trend = 0.0
    else:
        vals = [s["residual"] for s in series]
        w, tw, acc = 1.0, 0.0, 0.0
        for v in reversed(vals):          # frissebb meccs nagyobb súllyal
            acc += v * w
            tw += w
            w *= 0.6
        level = acc / tw
        n = len(vals)
        if n >= 2:
            mx = (n - 1) / 2.0
            my = sum(vals) / n
            num = sum((i - mx) * (v - my) for i, v in enumerate(vals))
            den = sum((i - mx) ** 2 for i in range(n))
            trend = num / den if den else 0.0
        else:
            trend = 0.0

    mult = 1.0 + PARAMS["form_level"] * level + PARAMS["form_trend"] * trend
    mult = max(0.8, min(1.2, mult))
    if with_details:
        return mult, {"mult": round(mult, 3), "level": round(level, 2),
                      "trend": round(trend, 2), "series": series}
    return mult


# ==============================================================================
# MECCS VALÓSZÍNŰSÉG SZÁMÍTÁS
# ==============================================================================

def _poisson_pmf(lam, k):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def poisson_matrix(eff_a, eff_b, scale=1.0):
    """
    A két effektív erőből várható gólszám (lambda), abból teljes
    eredmény-eloszlás. A döntetlen NEM utólagos levonás, hanem természetesen
    adódik a P(0-0)+P(1-1)+P(2-2)+... összegből.
    """
    base = PARAMS["poisson_base_goals"] * scale
    s = PARAMS["poisson_strength"]
    diff = eff_a - eff_b
    lam_a = max(0.02, base * math.exp(s * diff))
    lam_b = max(0.02, base * math.exp(-s * diff))
    n = int(PARAMS["poisson_max_goals"])
    pa = [_poisson_pmf(lam_a, k) for k in range(n + 1)]
    pb = [_poisson_pmf(lam_b, k) for k in range(n + 1)]
    p_win = p_draw = p_loss = 0.0
    best, best_p = (0, 0), 0.0
    for i in range(n + 1):
        for j in range(n + 1):
            p = pa[i] * pb[j]
            if p > best_p:
                best_p, best = p, (i, j)
            if i > j:
                p_win += p
            elif i == j:
                p_draw += p
            else:
                p_loss += p
    tot = p_win + p_draw + p_loss
    return (p_win / tot, p_draw / tot, p_loss / tot,
            {"lambda_a": round(lam_a, 2), "lambda_b": round(lam_b, 2),
             "likely_score": f"{best[0]}–{best[1]}",
             "likely_score_prob": round(best_p / tot * 100, 1)})


def score_prediction(team_a, team_b, round_name, results_so_far, gpt_modifiers=None):
    """A legvalószínűbb pontos eredmény (csak Poisson-motorral értelmes)."""
    ea, eb = _effective_strengths(team_a, team_b, round_name, results_so_far,
                                  gpt_modifiers)
    return poisson_matrix(ea, eb)[3]


def _effective_strengths(team_a, team_b, round_name, results_so_far, gpt_modifiers):
    """A két csapat effektív ereje (közös rész mindkét motorhoz).
    Bronzmeccsen (round_name='bronze') NINCS nyomás/momentum/forma — tét
    nélküli meccs, csak a nyers csapaterő + taktika számít. Ez tudatosan
    óvatosabb, mert a bronzmeccs a legkevésbé megjósolható meccstípus."""
    str_a = compute_base_strength(team_a, gpt_modifiers)
    str_b = compute_base_strength(team_b, gpt_modifiers)
    if round_name == "bronze":
        eff_a, eff_b = str_a, str_b
    else:
        eff_a = (str_a * compute_momentum(team_a, results_so_far)
                 * compute_pressure_factor(team_a, round_name)
                 * compute_form(team_a, results_so_far))
        eff_b = (str_b * compute_momentum(team_b, results_so_far)
                 * compute_pressure_factor(team_b, round_name)
                 * compute_form(team_b, results_so_far))
    tac_a = TEAMS.get(team_a, {}).get("tactical_style", "possession")
    tac_b = TEAMS.get(team_b, {}).get("tactical_style", "possession")
    eff_a += TACTIC_MATRIX.get((tac_a, tac_b), 0.0) * PARAMS["tactic_scale"]
    eff_b += TACTIC_MATRIX.get((tac_b, tac_a), 0.0) * PARAMS["tactic_scale"]
    return eff_a, eff_b


def match_probability(team_a, team_b, round_name, results_so_far, gpt_modifiers=None):
    """
    Kiszámolja a team_a győzelmének valószínűségét team_b ellen.

    Returns: (p_a_wins, p_draw, p_b_wins)
    """
    if ENGINE == "poisson":
        eff_a, eff_b = _effective_strengths(team_a, team_b, round_name,
                                            results_so_far, gpt_modifiers)
        p_a, p_draw, p_b, _ = poisson_matrix(eff_a, eff_b)
        if round_name != "group":
            # Kieséses szakasz, HELYES ág (v0.9):
            #   rendes játékidő döntetlen -> HOSSZABBÍTÁS: újabb Poisson-húzás
            #   30 percre (lambda arányosan rövidebb) -> ha az is döntetlen,
            #   TIZENEGYESEK: közel érmefeldobás, minimális erő-billenéssel.
            et_scale = PARAMS["poisson_et_scale"]          # 30/90 körül
            eta, etb, _ = poisson_matrix(eff_a, eff_b, scale=et_scale)[:3]
            # tizenegyes: alig függ az erőtől
            pen_a = 0.5 + PARAMS["poisson_pen_edge"] * (
                1.0 / (1.0 + 10 ** (-(eff_a - eff_b) / 25.0)) - 0.5)
            # hosszabbításbeli döntetlen -> tizenegyes
            et_draw = max(0.0, 1.0 - eta - etb)
            p_a_ko = eta + et_draw * pen_a
            p_b_ko = etb + et_draw * (1.0 - pen_a)
            tot_ko = p_a_ko + p_b_ko
            p_a = p_a + p_draw * (p_a_ko / tot_ko)
            p_b = p_b + p_draw * (p_b_ko / tot_ko)
            p_draw = 0.0
        return p_a, p_draw, p_b

    str_a = compute_base_strength(team_a, gpt_modifiers)
    eff_a, eff_b = _effective_strengths(team_a, team_b, round_name,
                                        results_so_far, gpt_modifiers)

    # ELO-szerű valószínűség
    elo_diff = eff_a - eff_b
    p_a = 1.0 / (1.0 + 10 ** (-elo_diff / PARAMS["elo_divisor"]))
    p_b = 1.0 - p_a

    # Döntetlen valószínűség (csak csoportkörben releváns)
    if round_name == "group":
        draw_base = PARAMS["draw_base"]
        draw_adj = draw_base * (1.0 - abs(elo_diff) / 100.0)
        draw_adj = max(0.05, min(0.35, draw_adj))
        p_a_adj = p_a * (1.0 - draw_adj)
        p_b_adj = p_b * (1.0 - draw_adj)
        return (p_a_adj, draw_adj, p_b_adj)
    else:
        # Kieséses / bronze: nincs döntetlen a kimenetben
        return (p_a, 0.0, p_b)


# ==============================================================================
# TORNA SZIMULÁCIÓ
# ==============================================================================

def simulate_group_stage(results_so_far, gpt_modifiers=None):
    """
    Szimulálja a csoportkört és visszaadja a továbbjutókat.
    Ha az eredmény már ismert, azt veszi figyelembe.
    """
    # Csoportok összeállítása
    groups = defaultdict(list)
    for team, data in TEAMS.items():
        groups[data["group"]].append(team)

    # Ismert eredmények feldolgozása
    played_ids = {r["match_id"] for r in results_so_far}
    group_standings = defaultdict(lambda: defaultdict(lambda: {
        "pts": 0, "gf": 0, "ga": 0, "gd": 0, "w": 0, "d": 0, "l": 0
    }))

    for r in results_so_far:
        if r.get("round") in [1, 2, 3]:
            home, away = r["home"], r["away"]
            hg, ag = r.get("home_goals", 0), r.get("away_goals", 0)
            group = TEAMS.get(home, {}).get("group", "?")

            group_standings[group][home]["gf"] += hg
            group_standings[group][home]["ga"] += ag
            group_standings[group][home]["gd"] += hg - ag
            group_standings[group][away]["gf"] += ag
            group_standings[group][away]["ga"] += hg
            group_standings[group][away]["gd"] += ag - hg

            if hg > ag:
                group_standings[group][home]["pts"] += 3
                group_standings[group][home]["w"] += 1
                group_standings[group][away]["l"] += 1
            elif hg < ag:
                group_standings[group][away]["pts"] += 3
                group_standings[group][away]["w"] += 1
                group_standings[group][home]["l"] += 1
            else:
                group_standings[group][home]["pts"] += 1
                group_standings[group][home]["d"] += 1
                group_standings[group][away]["pts"] += 1
                group_standings[group][away]["d"] += 1

    # Továbbjutók meghatározása (top 2 csoportonként + 8 legjobb 3.)
    qualifiers = {}
    third_place_teams = []

    for group_id in sorted(groups.keys()):
        teams_in_group = groups[group_id]
        standings = [(t, group_standings[group_id][t]) for t in teams_in_group]
        standings.sort(key=lambda x: (-x[1]["pts"], -x[1]["gd"], -x[1]["gf"]))

        qualifiers[f"{group_id}1"] = standings[0][0]
        qualifiers[f"{group_id}2"] = standings[1][0]
        if len(standings) > 2:
            third_place_teams.append((standings[2][0], standings[2][1]))

    # Legjobb 8 harmadik helyezett
    third_place_teams.sort(key=lambda x: (-x[0][1]["pts"], -x[0][1]["gd"], -x[0][1]["gf"])
                           if isinstance(x[0], tuple) else (-x[1]["pts"], -x[1]["gd"], -x[1]["gf"]))
    # Egyszerűsítve: top 8 harmadik
    for i, (team, _) in enumerate(third_place_teams[:8]):
        qualifiers[f"3rd_{i+1}"] = team

    return qualifiers


def simulate_knockout_bracket(remaining_teams, results_so_far, gpt_modifiers=None, rng=None):
    """
    Szimulálja a kieséses szakaszt a megmaradt csapatoktól.
    
    Args:
        remaining_teams: list of team names still in tournament
        results_so_far: eddigi eredmények
        gpt_modifiers: GPT-alapú erő-módosítók
        rng: random.Random instance
    
    Returns: dict {position: team_name}
    """
    if rng is None:
        rng = random.Random()

    teams = list(remaining_teams)
    placements = {}

    # Ismert kieséses eredmények feldolgozása
    known_knockout = {r["match_id"]: r for r in results_so_far
                      if r.get("round") in ["R32", "R16", "QF", "SF", "FINAL"]}

    # Elődöntők - ismert párosítások
    sf_teams = []
    for sf_id, sf_info in SEMIFINAL_MATCHUPS.items():
        if sf_id in known_knockout:
            r = known_knockout[sf_id]
            winner = r.get("winner")
            loser = sf_info["home"] if winner == sf_info["away"] else sf_info["away"]
            if winner:
                sf_teams.append(winner)
                placements[f"sf_loser_{sf_id}"] = loser
        else:
            # Szimulálás
            home, away = sf_info["home"], sf_info["away"]
            if home in teams and away in teams:
                p_home, _, p_away = match_probability(
                    home, away, "SF", results_so_far, gpt_modifiers
                )
                winner = home if rng.random() < p_home else away
                loser = away if winner == home else home
                sf_teams.append(winner)
                placements[f"sf_loser_{sf_id}"] = loser

    # Döntő
    if "FINAL" in known_knockout:
        r = known_knockout["FINAL"]
        winner = r.get("winner")
        finalist1 = r.get("home")
        finalist2 = r.get("away")
        runner_up = finalist2 if winner == finalist1 else finalist1
        placements["winner"] = winner
        placements["runner_up"] = runner_up
    elif len(sf_teams) == 2:
        finalist1, finalist2 = sf_teams[0], sf_teams[1]
        p_f1, _, p_f2 = match_probability(
            finalist1, finalist2, "FINAL", results_so_far, gpt_modifiers
        )
        winner = finalist1 if rng.random() < p_f1 else finalist2
        runner_up = finalist2 if winner == finalist1 else finalist1
        placements["winner"] = winner
        placements["runner_up"] = runner_up

    return placements


def run_monte_carlo(n_simulations=5000, gpt_modifiers=None, verbose=False):
    """
    Monte Carlo szimuláció a torna kimenetelének meghatározásához.
    
    Returns: dict {team: {win_prob, top2_prob, top4_prob, top8_prob, avg_position}}
    """
    all_results = get_all_known_results()

    # Egyéni (GPT-frissített) eredmények hozzáadása
    try:
        from gpt_updater import load_custom_results
        custom = load_custom_results()
        existing_ids = {r["match_id"] for r in all_results}
        for r in custom:
            if r["match_id"] not in existing_ids:
                all_results.append(r)
    except Exception:
        pass

    # Megmaradt csapatok (nem kiesett)
    remaining = [t for t, d in TEAMS.items()
                 if d.get("eliminated_round") is None]

    # Frissítés az ismert kieséses eredmények alapján
    known_eliminated = set()
    for r in all_results:
        if r.get("round") in ["R32", "R16", "QF", "SF", "FINAL"]:
            winner = r.get("winner")
            home, away = r.get("home"), r.get("away")
            if home and home != winner:
                known_eliminated.add(home)
            if away and away != winner:
                known_eliminated.add(away)

    remaining = [t for t in remaining if t not in known_eliminated]

    if verbose:
        print(f"  Megmaradt csapatok ({len(remaining)}): {', '.join(remaining)}")

    # Statisztikák
    stats = defaultdict(lambda: {
        "wins": 0, "finals": 0, "semis": 0, "quarters": 0,
        "top8": 0, "positions": []
    })

    rng = random.Random(42)

    for sim in range(n_simulations):
        sim_rng = random.Random(rng.randint(0, 2**32))
        placements = simulate_knockout_bracket(
            remaining, all_results, gpt_modifiers, sim_rng
        )

        winner = placements.get("winner")
        runner_up = placements.get("runner_up")

        if winner:
            stats[winner]["wins"] += 1
            stats[winner]["finals"] += 1
            stats[winner]["semis"] += 1
            stats[winner]["quarters"] += 1
            stats[winner]["top8"] += 1
            stats[winner]["positions"].append(1)

        if runner_up:
            stats[runner_up]["finals"] += 1
            stats[runner_up]["semis"] += 1
            stats[runner_up]["quarters"] += 1
            stats[runner_up]["top8"] += 1
            stats[runner_up]["positions"].append(2)

        # SF vesztesek
        for key, team in placements.items():
            if key.startswith("sf_loser"):
                stats[team]["semis"] += 1
                stats[team]["quarters"] += 1
                stats[team]["top8"] += 1
                stats[team]["positions"].append(3)

    # Normalizálás
    results = {}
    for team in remaining:
        s = stats[team]
        results[team] = {
            "win_prob": s["wins"] / n_simulations * 100,
            "final_prob": s["finals"] / n_simulations * 100,
            "semi_prob": s["semis"] / n_simulations * 100,
            "quarter_prob": s["quarters"] / n_simulations * 100,
            "top8_prob": s["top8"] / n_simulations * 100,
            "avg_position": (sum(s["positions"]) / len(s["positions"])
                             if s["positions"] else 8),
        }

    # Kiesett csapatok hozzáadása (0% eséllyel)
    for team in TEAMS:
        if team not in results:
            elim = TEAMS[team].get("eliminated_round", "group")
            results[team] = {
                "win_prob": 0.0,
                "final_prob": 0.0,
                "semi_prob": 0.0,
                "quarter_prob": 0.0,
                "top8_prob": 0.0,
                "avg_position": {"group": 24, "R32": 17, "R16": 9,
                                 "QF": 5, "SF": 3}.get(elim, 24),
                "eliminated_round": elim,
            }

    return results


# ==============================================================================
# PREDIKCIÓ MEGJELENÍTÉSE
# ==============================================================================

def print_prediction(results, title="Predikció", top_n=10):
    """Predikció szép megjelenítése."""
    print(f"\n  ╔══════════════════════════════════════════════════════════╗")
    print(f"  ║  {title:<56}║")
    print(f"  ╠══════════════════════════════════════════════════════════╣")
    print(f"  ║  {'#':<3} {'Csapat':<20} {'Győzelem%':>9} {'Döntő%':>7} {'Elődöntő%':>10} ║")
    print(f"  ╠══════════════════════════════════════════════════════════╣")

    sorted_teams = sorted(
        [(t, d) for t, d in results.items() if d.get("win_prob", 0) > 0],
        key=lambda x: -x[1]["win_prob"]
    )

    for i, (team, data) in enumerate(sorted_teams[:top_n], 1):
        marker = "★" if i == 1 else ("►" if i <= 5 else " ")
        print(f"  ║ {marker}{i:<3} {team:<20} {data['win_prob']:>8.1f}% "
              f"{data['final_prob']:>6.1f}% {data['semi_prob']:>9.1f}% ║")

    print(f"  ╚══════════════════════════════════════════════════════════╝")


def get_top5_prediction(results):
    """Visszaadja a top 5 várható helyezettet."""
    sorted_teams = sorted(
        [(t, d) for t, d in results.items()],
        key=lambda x: (-x[1]["win_prob"], x[1]["avg_position"])
    )
    return [t for t, _ in sorted_teams[:5]]


# ==============================================================================
# VALIDÁCIÓ
# ==============================================================================

def validate_prediction(predicted_top5, actual_top5):
    """
    Összehasonlítja a predikciót a valós eredménnyel.
    
    Returns: dict {overlap, winner_correct, brier_score}
    """
    if not actual_top5:
        return {"error": "Nincs valós eredmény a validációhoz"}

    overlap = len(set(predicted_top5) & set(actual_top5))
    winner_correct = predicted_top5[0] == actual_top5[0] if actual_top5 else False

    return {
        "predicted_top5": predicted_top5,
        "actual_top5": actual_top5,
        "overlap": overlap,
        "overlap_pct": overlap / 5 * 100,
        "winner_correct": winner_correct,
    }

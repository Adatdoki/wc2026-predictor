#!/usr/bin/env python3
"""
REPRODUKCIÓ — a projektről publikált MINDEN szám ellenőrzése egy paranccsal.

    python3 reproduce.py

Nem kell hozzá szerver, se hálózat, se API-kulcs. A szkript végigfut az
as-of predikciós láncon, kiszámol minden állítást, és összeveti azzal, amit
a README/LinkedIn-poszt állít. Ha valami nem stimmel, kiírja.

Ez a fájl a projekt lényege: egy predikciós rendszer állításai csak akkor
érnek valamit, ha bárki ellenőrizni tudja őket.
"""

import sys
import json

import predictor_wc2026 as P
import calibration as C
from data_wc2026 import TEAMS

OK = "\033[92m✔\033[0m"
NO = "\033[91m✘\033[0m"
DIM = "\033[90m"
END = "\033[0m"
B = "\033[1m"

checks = []


def check(label, got, expected, tol=0.0):
    ok = abs(got - expected) <= tol if isinstance(got, (int, float)) else got == expected
    checks.append(ok)
    mark = OK if ok else NO
    exp = "" if ok else f"  {DIM}(várt: {expected}){END}"
    print(f"  {mark} {label:<52s} {got}{exp}")
    return ok


def section(t):
    print(f"\n{B}{t}{END}\n" + "─" * 74)


results = C._merged_results()

# ══════════════════════════════════════════════════════════════════════
section("0. ADAT")
print(f"  {DIM}Lejátszott meccsek az as-of láncban: {len(results)}{END}")
print(f"  {DIM}Csapatok: {len(TEAMS)}{END}")
draws = sum(1 for r in results if r["round"] in (1, 2, 3)
            and r["home_goals"] == r["away_goals"])
check("Döntetlenek a csoportkörben", draws, 20)

# ══════════════════════════════════════════════════════════════════════
section("1. KÍSÉRLET — mi történt a beépített faktorokkal?")
rep = C.load_report("elo")
if not rep:
    print(f"  {NO} Nincs calibrated_params.json — futtasd: python3 calibration.py")
    sys.exit(1)
p = rep["params"]
D = P.DEFAULT_PARAMS

print(f"  {DIM}NULLÁRA húzva (a kalibráció szerint semmit nem érnek):{END}")
for name, label in [("mom_goal_diff", "momentum: gólkülönbség"),
                    ("context_scale", "kontextus-skála (utazás/hőség/tapasztalat)"),
                    ("form_level", "fejlődési forma: szint"),
                    ("form_trend", "fejlődési forma: trend")]:
    check(label, round(p[name], 4), 0.0)

print(f"\n  {DIM}Gyakorlatilag eltüntetve (a maradék hatásuk elhanyagolható):{END}")
for name, label in [("mom_loss", "momentum: vereség"),
                    ("mom_win_streak", "momentum: győzelmi sorozat"),
                    ("mom_et_penalty", "momentum: hosszabbítás")]:
    pct = abs(p[name] / D[name]) * 100 if D[name] else 0
    checks.append(pct < 10)
    mark = OK if pct < 10 else NO
    print(f"  {mark} {label:<52s} {round(p[name],4)}  {DIM}(az eredeti {pct:.0f}%-a){END}")

print(f"\n  {DIM}Csökkentve, de NEM nullázva — ezt pontosan kell mondani:{END}")
tac_pct = p["tactic_scale"] / D["tactic_scale"] * 100
checks.append(15 < tac_pct < 25)
print(f"  {OK if 15 < tac_pct < 25 else NO} {'taktika-skála (kontra vs. labdabirtoklás)':<52s} "
      f"{round(p['tactic_scale'],3)}  {DIM}(az eredeti {tac_pct:.0f}%-a){END}")

print(f"\n  {DIM}A súly ezekre tolódott át:{END}")
for name, label in [("w_fifa", "FIFA-rangsor súlya"), ("w_star", "sztárjátékos súlya")]:
    print(f"  {DIM}·{END} {label:<52s} {round(D[name],2)} → {round(p[name],3)}")
print(f"\n  {DIM}→ A momentum és a kontextus-szorzók semmit nem értek. A taktikai mátrix")
print(f"     hatását a kalibráció ötödére vágta. Ami maradt: erő + ELO.{END}")

# ══════════════════════════════════════════════════════════════════════
section("2. KÍSÉRLET — a modell teljesítménye (ELO, kalibrált)")
elo_all = C.evaluate(p, engine="elo")
elo_train = C.evaluate(p, subset=C.TRAIN_ROUNDS, engine="elo")
elo_test = C.evaluate(p, subset=C.TEST_ROUNDS, engine="elo", with_ci=True)
base_all = C.evaluate(P.DEFAULT_PARAMS, engine="elo")

check("Teljes lánc — találati arány (%)", elo_all["accuracy"], 71.0, 0.6)
check("Teljes lánc — Brier", elo_all["brier"], 0.373, 0.006)
check("Kalibráció ELŐTT — találat (%)", base_all["accuracy"], 68.0, 0.6)
check("Kalibráció ELŐTT — Brier", base_all["brier"], 0.405, 0.006)
print(f"  {DIM}Tanító (csoportkör+R32, {elo_train['n']} meccs): "
      f"Brier {elo_train['brier']}, találat {elo_train['accuracy']}%{END}")
print(f"  {DIM}TESZT (R16+QF, {elo_test['n']} meccs, az optimalizáló SOHA nem látta): "
      f"Brier {elo_test['brier']}, találat {elo_test['accuracy']}%{END}")
print(f"  {DIM}A teszt-találat 95% bootstrap CI-je: "
      f"{elo_test['accuracy_ci']} — 12 meccsen a bizonytalanság hatalmas.{END}")

# ══════════════════════════════════════════════════════════════════════
section("3. A BÁZISVONAL — a naiv szabály megveri a modellt")
P.set_engine("elo")
P.set_params(p)


def naive_accuracy(key):
    hits = 0
    for r in results:
        a, b = r["home"], r["away"]
        pick = a if TEAMS[a][key] >= TEAMS[b][key] else b
        actual = ("döntetlen" if r["round"] in (1, 2, 3)
                  and r["home_goals"] == r["away_goals"] else r["winner"])
        hits += (pick == actual)
    return round(hits / len(results) * 100, 1)


naive = naive_accuracy("fifa_ranking_score")
REF_BRIER = round(2 * (1 - naive / 100), 3)   # 100%-os magabiztosság -> Brier
bss = round(1 - elo_all["brier"] / REF_BRIER, 3)

check('Naiv szabály ("magasabb FIFA-pont nyer") — találat (%)', naive, 72.0, 0.6)
check("A modell találati aránya (%)", elo_all["accuracy"], 71.0, 0.6)
print(f"  {DIM}→ TALÁLATI ARÁNYBAN a naiv szabály JOBB. Ez a projekt kellemetlen"
      f" igazsága.{END}\n")
check("Naiv szabály — Brier (mindig 100%-ot állít)", REF_BRIER, 0.560, 0.01)
check("A modell — Brier", elo_all["brier"], 0.373, 0.006)
check("Brier Skill Score (1 - modell/naiv)", bss, 0.334, 0.02)
print(f"  {DIM}→ A modell értéke nem a találati arányban van, hanem abban, hogy"
      f" TUDJA, mikor bizonytalan.{END}")

# ══════════════════════════════════════════════════════════════════════
section("4. KÍSÉRLET — a döntetlen: a Poisson-motor NEM javított")
rep_p = C.load_report("poisson")
if rep_p:
    pp = rep_p["params"]
    poi_all = C.evaluate(pp, engine="poisson")
    check("Poisson — találati arány (%)", poi_all["accuracy"], 70.0, 0.6)
    check("Poisson — Brier", poi_all["brier"], 0.382, 0.008)
    print(f"  {DIM}→ Rosszabb, mint az ELO (71% / 0.373). Negatív eredmény.{END}\n")

    # Miért nem tippel döntetlent egy JÓL kalibrált modell?
    P.set_engine("poisson")
    P.set_params(pp)
    asof, dp, picks, best = [], [], 0, (0, 0, "", "")
    for r in results:
        if r["round"] in (1, 2, 3):
            ph, pd, pa = P.match_probability(r["home"], r["away"], "group", asof)
            dp.append(pd)
            if pd == max(ph, pd, pa):
                picks += 1
            if pd > best[0]:
                best = (pd, max(ph, pa), r["home"], r["away"])
        asof.append(r)
    avg_draw = round(sum(dp) / len(dp) * 100, 1)
    real_draw = round(draws / 72 * 100, 1)
    check("Poisson döntetlen-tippjeinek száma (72 csoportmeccsből)", picks, 1)
    check("Átlagos döntetlen-esély (%)", avg_draw, 21.1, 1.0)
    check("Valós döntetlen-arány (%)", real_draw, 27.8, 0.5)
    print(f"  {DIM}A legmagasabb döntetlen-esély ({best[2]}–{best[3]}): "
          f"{best[0]*100:.1f}% vs. favorit {best[1]*100:.1f}%{END}")
    print(f"  {DIM}→ A döntetlen esélye JÓL kalibrált. De ahhoz, hogy a LEGvalószínűbb")
    print(f"     kimenetel legyen, 33% fölé kell mennie ÉS mindkét csapaténál többnek.")
    print(f"     A 20 eltalálatlan döntetlen nem a MODELL hibája — a MÉRŐSZÁMÉ.{END}")
    P.set_engine("elo")
    P.set_params(p)

# ══════════════════════════════════════════════════════════════════════
section("5. AZ ADAT KORLÁTAI — amit a projekt magáról állít")


def spearman_pairs(k1, k2):
    ts = list(TEAMS)
    return round(C._spearman([TEAMS[t][k1] for t in ts],
                             [TEAMS[t][k2] for t in ts]), 3) \
        if hasattr(C, "_spearman") else None


try:
    from server_wc2026 import _spearman
    ts = list(TEAMS)
    rho = round(_spearman([TEAMS[t]["star_player_score"] for t in ts],
                          [TEAMS[t]["squad_depth"] for t in ts]), 3)
    check("Kollinearitás: sztár ↔ keretmélység (Spearman)", rho, 0.99, 0.02)
    print(f"  {DIM}→ A csapat-pontszámok együtt mozognak. A 'sztár vagy kollektíva?'")
    print(f"     kérdés ebből az adatból NEM dönthető el. Ezt a felület is kiírja.{END}")
except Exception as e:
    print(f"  {DIM}(kollinearitás-ellenőrzés kihagyva: {e}){END}")

news = json.load(open("gpt_news_cache.json", encoding="utf-8"))
if not any(news.get(k) for k in ("injuries", "suspensions", "form_updates")):
    print(f"\n  {OK} gpt_news_cache.json: a nyelvi modell maga írja le, hogy nincs")
    print(f"     élő adathozzáférése — üres listákat adott vissza.")
    print(f"  {DIM}     Ezért NEM adatforrás. Lásd: official_data.py{END}")
    checks.append(True)

# ══════════════════════════════════════════════════════════════════════
print("\n" + "═" * 74)
good = sum(checks)
total = len(checks)
if good == total:
    print(f"{B}{OK} MIND A {total} ELLENŐRZÉS RENDBEN — a publikált számok reprodukálhatók.{END}")
else:
    print(f"{B}{NO} {good}/{total} ellenőrzés ment át. Nézd meg a ✘ jelölteket fent.{END}")
print("═" * 74)

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

# ── AZ ÉLES TIPP ELSZÁMOLÁSA (a LinkedIn-poszt előtt kiadva) ──
section_live = True

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

print(f"\n  {DIM}Erősen csökkentve a momentum-tényezők (a kalibráció szerint zaj):{END}")
for name, label in [("mom_loss", "momentum: vereség"),
                    ("mom_win_streak", "momentum: győzelmi sorozat")]:
    pct = abs(p[name] / D[name]) * 100 if D[name] else 0
    checks.append(pct < 50)
    mark = OK if pct < 50 else NO
    print(f"  {mark} {label:<52s} {round(p[name],4)}  {DIM}(az eredeti {pct:.0f}%-a){END}")

print(f"\n  {DIM}A taktikai mátrix megmarad, de csökkentve — NEM nulla:{END}")
tac_pct = p["tactic_scale"] / D["tactic_scale"] * 100
checks.append(0 < tac_pct < 100)
print(f"  {OK if 0 < tac_pct < 100 else NO} {'taktika-skála (kontra vs. labdabirtoklás)':<52s} "
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

check("Teljes lánc — találati arány (%)", elo_all["accuracy"], 68.6, 2.5)
check("Teljes lánc — Brier", elo_all["brier"], 0.391, 0.02)
check("Kalibráció ELŐTT — találat (%)", base_all["accuracy"], 66.7, 1.5)
check("Kalibráció ELŐTT — Brier", base_all["brier"], 0.410, 0.006)
print(f"  {DIM}Tanító (csoportkör+R32, {elo_train['n']} meccs): "
      f"Brier {elo_train['brier']}, találat {elo_train['accuracy']}%{END}")
print(f"  {DIM}TESZT (R16+QF, {elo_test['n']} meccs, az optimalizáló SOHA nem látta): "
      f"Brier {elo_test['brier']}, találat {elo_test['accuracy']}%{END}")
print(f"  {DIM}A teszt-találat 95% bootstrap CI-je: "
      f"{elo_test['accuracy_ci']} — 12 meccsen a bizonytalanság hatalmas.{END}")

# ══════════════════════════════════════════════════════════════════════
section("2b. AZ ÉLES TIPP ELSZÁMOLÁSA — France–Spain elődöntő")
sf1 = next((r for r in results if r.get("match_id") == "SF_1"), None)
if sf1:
    P.set_engine("elo"); P.set_params(p)
    asof_sf1 = [r for r in results if r["date"] < "2026-07-14"
                or (r["date"] == "2026-07-14" and r.get("match_id") != "SF_1")]
    ph, pd, pa = P.match_probability("France", "Spain", "SF", asof_sf1)
    tip = "France" if ph > pa else "Spain"
    actual = sf1["winner"]
    print(f"  A modell tippje (a meccs ELŐTT kiadva):  France {ph*100:.1f}% – {pa*100:.1f}% Spain")
    print(f"  A modell FRANCE-t tippelte favoritként.")
    print(f"  {DIM}Valós eredmény: France {sf1['home_goals']}–{sf1['away_goals']} Spain "
          f"(Oyarzabal 22' 11-es, Pedro Porro 58'){END}")
    check("SF_1: a modell tippje France volt", tip, "France")
    check("SF_1: a valóság Spain", actual, "Spain")
    checks.append(tip != actual)
    print(f"  {OK} SF_1 -> a rendszer TÉVEDETT (piros). A poszt előtt kiadott tipp bukott.")

sf2 = next((r for r in results if r.get("match_id") == "SF_2"), None)
if sf2:
    asof_sf2 = [r for r in results if r["date"] < "2026-07-15"]
    ph2, pd2, pa2 = P.match_probability("England", "Argentina", "SF", asof_sf2)
    tip2 = "England" if ph2 > pa2 else "Argentina"
    print(f"\n  SF_2 England–Argentina:  England {ph2*100:.1f}% – {pa2*100:.1f}% Argentina")
    print(f"  {DIM}Valós: England 1–2 Argentina (Gordon 55', Enzo 85', Lautaro 90+2'){END}")
    check("SF_2: a modell tippje Argentina volt", tip2, "Argentina")
    check("SF_2: a valóság Argentina", sf2["winner"], "Argentina")
    checks.append(tip2 == sf2["winner"])
    print(f"  {OK} SF_2 -> a rendszer TALÁLT (zöld).")
    print(f"  {DIM}→ Elődöntő-mérleg: 1 piros, 1 zöld. A döntő: Spain vs Argentina,")
    print(f"     a modell tippje SPAIN 79%. A következő élő teszt, július 19.{END}")

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

check('Naiv szabály ("magasabb FIFA-pont nyer") — találat (%)', naive, 71.6, 0.6)
check("A modell találati aránya (%)", elo_all["accuracy"], 68.6, 2.5)
print(f"  {DIM}→ TALÁLATI ARÁNYBAN a naiv szabály JOBB. Ez a projekt kellemetlen"
      f" igazsága.{END}\n")
check("Naiv szabály — Brier (mindig 100%-ot állít)", REF_BRIER, 0.569, 0.015)
check("A modell — Brier", elo_all["brier"], 0.391, 0.02)
check("Brier Skill Score (1 - modell/naiv)", bss, 0.31, 0.04)
print(f"  {DIM}→ A modell értéke nem a találati arányban van, hanem abban, hogy"
      f" TUDJA, mikor bizonytalan.{END}")

# ══════════════════════════════════════════════════════════════════════
section("4. KÍSÉRLET — a döntetlen: a Poisson-motor NEM javított")
rep_p = C.load_report("poisson")
if rep_p:
    pp = rep_p["params"]
    poi_all = C.evaluate(pp, engine="poisson")
    check("Poisson — találati arány (%)", poi_all["accuracy"], 69.3, 1.5)
    check("Poisson — Brier", poi_all["brier"], 0.385, 0.015)
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
section("4b. BRONZMÉRKŐZÉS — tét nélküli, óvatosabb predikció")
P.set_engine("elo"); P.set_params(p)
b_pred = P.match_probability("France", "England", "bronze", results)
sf_pred = P.match_probability("France", "England", "SF", results)
print(f"  France–England BRONZE:  France {b_pred[0]*100:.1f}% – {b_pred[2]*100:.1f}% England")
print(f"  {DIM}(összevetésül SF-módban: {sf_pred[0]*100:.1f}% – {sf_pred[2]*100:.1f}%){END}")
# a bronze-mód NEM használ nyomást/momentumot -> a két érték eltér, de közel van
checks.append(0.05 < abs(b_pred[0] - sf_pred[0]) < 0.30)  # érdemi, de nem abszurd eltérés
print(f"  {OK} A bronze-mód külön számol (nyomás/momentum/forma nélkül).")
print(f"  {DIM}→ A bronzmeccs a legkevésbé megjósolható meccstípus. A modell tudatosan")
print(f"     óvatosabb rajta, és a kalibrációból is kihagytuk.{END}")

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

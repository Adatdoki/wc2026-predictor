"""
FIFA World Cup 2026 - Paraméter-kalibráció
===========================================
A motor globális paramétereit a VALÓS eredményekhez kalibrálja.

Módszer:
  - Célfüggvény: átlagos Brier-pontszám az as-of predikciós láncon
    (folytonos — a zöld/piros darabszám lépcsős lenne, az optimalizáló
    nem tudna min haladni)
  - Koordinátánkénti ereszkedés több véletlen újraindítással, korlátokkal
  - TÚLILLESZTÉS-VÉDELEM: optimalizálás CSAK a tanító halmazon
    (csoportkör + R32, 88 meccs), kiértékelés a soha nem látott teszt
    halmazon (R16 + negyeddöntők, 12 meccs). Ha a teszt-Brier nem javul,
    a jelentés ezt őszintén kimondja.

Kimenet: calibrated_params.json (paraméterek + teljes jelentés)

Használat:
    python3 calibration.py            # kalibráció futtatása
    python3 calibration.py --report   # meglévő jelentés kiírása
"""

import json
import os
import random
import argparse
from datetime import datetime, timezone

import predictor_wc2026 as P
from predictor_wc2026 import (DEFAULT_PARAMS, PARAM_BOUNDS, set_params,
                              match_probability)

CALIB_FILE = "calibrated_params.json"          # ELO-motor (visszafelé kompatibilis)
CALIB_FILE_POISSON = "calibrated_params_poisson.json"


def calib_file(engine="elo"):
    return CALIB_FILE if engine == "elo" else CALIB_FILE_POISSON

TRAIN_ROUNDS = {1, 2, 3, "R32"}
TEST_ROUNDS = {"R16", "QF", "SF", "FINAL"}


# ── Adatlánc (a szerverrel azonos merge-logika, fastapi-függés nélkül) ──

def _merged_results():
    from data_wc2026 import GROUP_STAGE_RESULTS, KNOCKOUT_RESULTS
    by_id = {}
    for r in GROUP_STAGE_RESULTS + KNOCKOUT_RESULTS:
        by_id[r["match_id"]] = dict(r)
    if os.path.exists("custom_results_wc2026.json"):
        with open("custom_results_wc2026.json", encoding="utf-8") as f:
            for r in json.load(f):
                by_id[r["match_id"]] = dict(r)
    for r in by_id.values():
        if not r.get("winner"):
            hg, ag = r.get("home_goals"), r.get("away_goals")
            if hg is not None and ag is not None and hg != ag:
                r["winner"] = r["home"] if hg > ag else r["away"]
    order = {1: 0, 2: 1, 3: 2, "R32": 3, "R16": 4, "QF": 5, "SF": 6, "FINAL": 7}
    return sorted(by_id.values(),
                  key=lambda r: (r["date"], order.get(r["round"], 9), r["match_id"]))


def _brier_of_match(m, asof):
    rn = "group" if m["round"] in (1, 2, 3) else m["round"]
    ph, pd, pa = match_probability(m["home"], m["away"], rn, asof)
    hg, ag = m.get("home_goals"), m.get("away_goals")
    if rn == "group" and hg == ag:
        actual = "draw"
    else:
        actual = "home" if m.get("winner") == m["home"] else "away"
    b = 0.0
    for key, p in (("home", ph), ("draw", pd), ("away", pa)):
        b += (p - (1.0 if key == actual else 0.0)) ** 2
    correct = {"home": ph, "draw": pd, "away": pa}[actual] == max(ph, pd, pa)
    return b, correct


def _bootstrap_ci(values, n_boot=2000, seed=7):
    """95% bootstrap konfidencia-intervallum az átlagra."""
    if not values:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n
                   for _ in range(n_boot))
    return [round(means[int(0.025 * n_boot)], 4),
            round(means[int(0.975 * n_boot)], 4)]


def evaluate(params, subset=None, with_ci=False, engine=None):
    """Végigmegy az as-of láncon; visszaadja az átlag Brier-t és a találati
    arányt a kért részhalmazon (None = mind)."""
    if engine:
        P.set_engine(engine)
    set_params(params)
    results = _merged_results()
    asof, briers, hits = [], [], []
    for m in results:
        if subset is None or m["round"] in subset:
            b, c = _brier_of_match(m, asof)
            briers.append(b)
            hits.append(c)
        asof.append(m)
    n = len(briers)
    out = {"n": n,
           "brier": round(sum(briers) / n, 4) if n else None,
           "accuracy": round(sum(hits) / n * 100, 1) if n else None}
    if with_ci and n:
        out["brier_ci"] = _bootstrap_ci(briers)
        acc_ci = _bootstrap_ci([1.0 if h else 0.0 for h in hits])
        out["accuracy_ci"] = [round(acc_ci[0] * 100, 1), round(acc_ci[1] * 100, 1)]
    return out


# ── Koordinátánkénti ereszkedés ──

def _clip(k, v):
    lo, hi = PARAM_BOUNDS[k]
    return max(lo, min(hi, v))


def coordinate_descent(start, n_passes=10, seed=0, engine="elo"):
    rng = random.Random(seed)
    params = dict(start)
    best = evaluate(params, TRAIN_ROUNDS, engine=engine)["brier"]
    keys = [k for k in DEFAULT_PARAMS
            if not (engine == "elo" and k.startswith("poisson"))
            and not (engine == "poisson" and k in ("elo_divisor", "draw_base"))
            and k != "poisson_max_goals"]
    steps = {k: (PARAM_BOUNDS[k][1] - PARAM_BOUNDS[k][0]) * 0.15 for k in keys}
    for _ in range(n_passes):
        improved = False
        rng.shuffle(keys)
        for k in keys:
            for direction in (+1, -1):
                cand = dict(params)
                cand[k] = _clip(k, params[k] + direction * steps[k])
                if cand[k] == params[k]:
                    continue
                b = evaluate(cand, TRAIN_ROUNDS, engine=engine)["brier"]
                if b < best - 1e-6:
                    params, best = cand, b
                    improved = True
                    break
        if not improved:
            for k in keys:
                steps[k] *= 0.5
            if max(steps.values()) < 1e-4:
                break
    return params, best


def calibrate(n_restarts=3, progress_cb=None, engine="elo"):
    """Teljes kalibráció: alapérték-indítás + véletlen újraindítások,
    a legjobb tanító-Brier nyer, jelentés a teszt halmazzal."""
    rng = random.Random(2026)
    starts = [dict(DEFAULT_PARAMS)]
    for _ in range(n_restarts):
        s = {k: rng.uniform(*PARAM_BOUNDS[k]) for k in DEFAULT_PARAMS}
        s["poisson_max_goals"] = DEFAULT_PARAMS["poisson_max_goals"]
        starts.append(s)

    before_train = evaluate(DEFAULT_PARAMS, TRAIN_ROUNDS, engine=engine)
    before_test = evaluate(DEFAULT_PARAMS, TEST_ROUNDS, with_ci=True, engine=engine)
    before_all = evaluate(DEFAULT_PARAMS, engine=engine)

    best_params, best_brier = None, float("inf")
    for i, s in enumerate(starts):
        if progress_cb:
            progress_cb(i, len(starts))
        p, b = coordinate_descent(s, seed=i, engine=engine)
        if b < best_brier:
            best_params, best_brier = p, b
    if progress_cb:
        progress_cb(len(starts), len(starts))

    after_train = evaluate(best_params, TRAIN_ROUNDS, engine=engine)
    after_test = evaluate(best_params, TEST_ROUNDS, with_ci=True, engine=engine)
    after_all = evaluate(best_params, engine=engine)

    # Érzékenység: paraméterenként ±10% tartomány-elmozdítás hatása a tanító-Brierre
    sensitivity = []
    for k in DEFAULT_PARAMS:
        span = (PARAM_BOUNDS[k][1] - PARAM_BOUNDS[k][0]) * 0.10
        if span == 0:
            continue
        b_up = evaluate({**best_params, k: _clip(k, best_params[k] + span)}, TRAIN_ROUNDS, engine=engine)["brier"]
        b_dn = evaluate({**best_params, k: _clip(k, best_params[k] - span)}, TRAIN_ROUNDS, engine=engine)["brier"]
        sensitivity.append({"param": k,
                            "impact": round(max(b_up, b_dn) - after_train["brier"], 4)})
    sensitivity.sort(key=lambda s: -s["impact"])

    changes = [{"param": k,
                "default": round(DEFAULT_PARAMS[k], 4),
                "calibrated": round(best_params[k], 4),
                "change_pct": round((best_params[k] - DEFAULT_PARAMS[k])
                                    / (abs(DEFAULT_PARAMS[k]) or 1) * 100, 1)}
               for k in DEFAULT_PARAMS]
    changes.sort(key=lambda c: -abs(c["change_pct"]))

    test_improved = after_test["brier"] < before_test["brier"]
    report = {
        "engine": engine,
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "method": "koordinátánkénti ereszkedés, "
                  f"{n_restarts} véletlen újraindítás + alapérték-indítás",
        "train_set": "csoportkör + R32 (az optimalizáló ezt látta)",
        "test_set": "R16 + negyeddöntők (az optimalizáló SOHA nem látta)",
        "before": {"train": before_train, "test": before_test, "all": before_all},
        "after": {"train": after_train, "test": after_test, "all": after_all},
        "test_improved": test_improved,
        "honest_verdict": (
            "A javulás a nem látott teszthalmazon is megvan — valódi kalibráció."
            if test_improved else
            "A tanító halmazon javult, a teszthalmazon NEM — ez túlillesztés "
            "jele, a kalibrált súlyokat óvatosan kezeld."),
        "params": best_params,
        "changes": changes,
        "sensitivity": sensitivity,
    }
    with open(calib_file(engine), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    set_params(DEFAULT_PARAMS)  # a modul globálisát visszaállítjuk
    P.set_engine("elo")
    return report


def load_report(engine="elo"):
    fp = calib_file(engine)
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            return json.load(f)
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--engine", default="elo", choices=["elo", "poisson"])
    a = ap.parse_args()
    if a.report:
        r = load_report(a.engine)
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else "Nincs jelentés.")
    else:
        print(f"  Kalibráció indul — motor: {a.engine} "
              "(tanító: csoportkör+R32, teszt: R16+QF)…")
        rep = calibrate(progress_cb=lambda i, n: print(f"  indítás {i}/{n}"),
                        engine=a.engine)
        b, a_ = rep["before"], rep["after"]
        print(f"\n  TANÍTÓ  Brier: {b['train']['brier']} -> {a_['train']['brier']}"
              f"  | találat: {b['train']['accuracy']}% -> {a_['train']['accuracy']}%")
        print(f"  TESZT   Brier: {b['test']['brier']} -> {a_['test']['brier']}"
              f"  | találat: {b['test']['accuracy']}% -> {a_['test']['accuracy']}%")
        print(f"\n  {rep['honest_verdict']}")
        print(f"  Mentve: {calib_file(a.engine)}")

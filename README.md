# WC2026 Predikciós Rendszer

Egy FIFA VB-2026 predikciós rendszer, ami **as-of** elven működik: bármelyik meccsre
visszaáll az adott pillanatba, és kizárólag az addigi eredményekből számol. A jövő
adata nem szivároghat vissza.

De ez a repo nem attól érdekes, hogy működik. Hanem attól, hogy **megmutatja, hol
nem működik.**

```bash
pip install fastapi uvicorn
python3 reproduce.py       # minden alábbi szám ellenőrzése, ~10 másodperc
python3 server_wc2026.py   # webfelület: http://localhost:8026
```

---

## 🔴 UTÓÉLET — az élő tipp elbukott (2026-07-14)

A LinkedIn-poszt előtt a rendszer nyilvánosan kiadta a France–Spain elődöntőre adott
tippjét: **France 73,7%.** Utólag nem szépíthető.

**Az eredmény: France 0–2 Spain** (Oyarzabal 22' tizenegyes, Pedro Porro 58').
A modell **tévedett** — határozott favoritot tippelt, aki kikapott. A felületen ez egy
piros pötty, a meccs Brier-pontszáma **1,09** (a lehető legrosszabb).

Ez a projekt legőszintébb pillanata, és a hatása mérhető:

- A teljes validáció most **101 meccs.** A modell találati aránya 71% → **70,3%**,
  a Brier Skill Score +0,334 → **+0,321**.
- A teszthalmaz 12 → **13 kieséses meccs** — és itt a lényeg: **a kalibráció ezen a
  bővebb teszthalmazon már NEM javít**, a rendszer maga jelzi ki a túlillesztést.
  Egyetlen rosszul eltalált, nagy magabiztosságú tipp elég volt, hogy megbillentse a
  képet. Pontosan ezért kell több adat, mint 100 meccs.
- A döntő láncolt predikciója frissült: France–Spain most **valós eredmény**, a döntőt
  **Spain (89,7%)** vezeti az England–Argentina győztese ellen.

Forrás: FIFA match report, Reuters, Al Jazeera (2026-07-14).

---

## ⚠️ ADAT-FIGYELMEZTETÉS — olvasd el, mielőtt bármit elhiszel

Ez a repo **nem megbízható VB-adatbázis.** Konkrétan:

- A `data_wc2026.py`-ben szereplő eredmények nagy részét **nem hitelesítettük** hivatalos
  forrással. A projekt elején egy nyelvi modell „gyűjtötte össze" őket, és **kettő
  hamis volt** (Brazil–Norway 1–2, nem 0–2; Argentina–Switzerland 3–1 rendes
  játékidőben, nem 0–3 hosszabbításban). Amit hitelesítettünk, azon `source: "official"`
  jelölés van (köztük a France–Spain elődöntő).
- A csapat-pontszámok (`star_player_score`, `squad_depth`, `coach_quality`)
  **generáltak**, és egymással **ρ ≈ 0,99** korrelációban mozognak. Ebből az adatból a
  „sztár vagy kollektíva?" kérdés **nem dönthető el** — a felület ezt ki is írja.
- Az eredmények hitelesítéséhez: `python3 official_data.py --fetch` (ingyenes kulcs a
  football-data.org-ról), majd `--verify` és `--sync`.

**A modell tanulságai ettől függetlenül állnak**, mert azok a modell *viselkedéséről*
szólnak, nem a konkrét csapatokról. De ha valós predikcióra használnád: előbb
hitelesítsd az adatot.

---

## Az eredmények (mind reprodukálható: `python3 reproduce.py`)

### 1. A beépített faktorok nagy részét a kalibráció megsemmisítette

15 paraméter, Brier-minimalizálás, szigorú tanító/teszt szétválasztással
(tanítás: csoportkör + R32; kiértékelés: R16 + negyeddöntők + elődöntő, amit az
optimalizáló **soha nem látott**).

A momentum-tényezők és a kontextus-szorzók (utazás, hőség, tapasztalat) hatását a
kalibráció nullára vagy a töredékére vágta. A fejlődési forma nullán maradt. A taktikai
mátrix megmarad, de csökkentve. **Ami maradt: csapaterő + ELO.** Minden „okos" faktor
jórészt zajnak bizonyult.

### 2. A naiv szabály megveri a modellt — találati arányban

| Módszer | Találat | Brier | Skill (BSS) |
|---|---|---|---|
| „Mindig a magasabb FIFA-pontszámú nyer" | **71,3%** | 0,574 | −0,025 |
| **A modell (kalibrált)** | 70,3% | **0,380** | **+0,321** |
| Csupasz alapmodell (erő + ELO) | 70,3% | 0,392 | +0,300 |
| Érmefeldobás | 44,6% | 0,619 | −0,105 |

Egy sornyi Excel-képlet jobb (vagy azonos) találati arányt ér el, mint a rendszer.

**De a naiv szabály mindig 100%-ot állít — nem tud bizonytalan lenni.** A modell esélyt
mond, és tudja, mikor bizonytalan: Brier 0,380 vs 0,574, **skill score +0,321**.

Ezért a felületen a **Brier Skill Score** a fő mérőszám, nem a találati arány. A projekt
lecserélte a saját mérőszámát, mert a rendszer bebizonyította, hogy rossz.

### 3. A döntetlen-vakság nem hiba — a mérőszám hibája

A modell 72 csoportmeccsből **egyszer** tippelt döntetlent (és eltalálta:
Paraguay–Australia). Közben 20 döntetlen volt.

Egy **Poisson-gólmodell** (ahol a döntetlen természetesen adódik a gólvárakozásból)
**nem javított.** De megmutatta, miért: a döntetlen esélye **jól kalibrált** (átlag
~21%, valós arány 27,8%), csak ahhoz, hogy a **legvalószínűbb** kimenetel legyen, 33%
fölé kell mennie **és** mindkét csapaténál többnek lennie. Ez szinte sosem teljesül.

**A 20 eltalálatlan döntetlen nem a modell hibája. A találati arány mint mérőszám
inherens plafonja.**

### 4. Egy LLM nem adatforrás

Az első verzió eredményeit egy nyelvi modell „gyűjtötte össze". A `gpt_news_cache.json`
fájlban a modell **maga írja le**, hogy nincs élő adathozzáférése — mégis adott
eredményeket, és **kettő hamis volt**. Megoldás: `official_data.py` (hivatalos forrás,
`--verify`, `--sync`). Az LLM szerepe leszűkült a **valós hírcikkek értelmezésére**.

### 5. Mit tudok és mit nem

- A teszthalmaz **13 meccs.** A kis mintán a bizonytalanság hatalmas — a rendszer
  bootstrap konfidencia-intervallumot ír ki, és kimondja, ha a kalibráció túlilleszt.
- A csapat-pontszámok kollineárisak (ρ≈0,99). A tényező-korrelációk CI-je teljesen
  átfed — a sorrendjük statisztikailag nem megkülönböztethető.

---

## A felület

| Nézet | Mit csinál |
|---|---|
| **Meccsek** | Idővonal. Kattintásra as-of predikció, gombnyomásra a valóság: zöld = talált, sárga = szoros, piros = tévedett. |
| **▶ Teljes validáció** | Végigpörgeti az összes lejátszott meccset, fordulónkénti bontással, megbízhatósági görbével, bázisvonal-táblázattal. |
| **⚖ Kalibráció** | Tanító/teszt kalibráció, jelentéssel. Kimondja, ha túlillesztés. |
| **📈 Top5 idővonal** | A győzelmi esélyek alakulása a torna alatt, időcsúszkával. |
| **🔬 Elemzés** | Sztár vs. kollektíva a valós eredményekből — konfidencia-intervallumokkal. |
| **ELO / Poisson** | Motorváltó. A Poisson pontos eredményt is jósol. |
| **🔄 Eredmény-frissítés** | Hivatalos letöltés → ellenőrzés → javítás → cache-ürítés, egy gombbal. |

---

## Fájlok

| Fájl | Szerep |
|---|---|
| `reproduce.py` | **Minden publikált szám ellenőrzése egy paranccsal** |
| `predictor_wc2026.py` | A motor: erő, momentum, nyomás, forma, ELO + Poisson |
| `calibration.py` | Koordinátánkénti ereszkedés, tanító/teszt szétválasztás, bootstrap CI |
| `server_wc2026.py` | FastAPI: as-of predikció, validáció, bázisvonalak, BSS |
| `frontend_wc2026.html` | A felület (egyetlen fájl, külső könyvtár nélkül) |
| `official_data.py` | Hivatalos adatforrás, `--verify`, `--sync` |
| `data_wc2026.py` | ⚠️ Csapatok és eredmények — lásd az adat-figyelmeztetést |
| `gpt_news_cache.json` | Bizonyíték: itt írja le a nyelvi modell, hogy nincs élő adata |
| `termux_*.sh` | Futtatás Androidon, lokálisan |

## Futtatás telefonon (Termux)

```bash
bash termux_setup.sh   # egyszeri telepítés (pydantic v1 fallbackkel)
bash termux_start.sh   # -> http://localhost:8026
```

A motornak csak `fastapi` + `uvicorn` kell — se numpy, se pandas.

---

## Licenc

MIT — lásd `LICENSE`.

## A tanulság

Egy predikciós rendszer első kérdése nem az, hogy hány százalék.
Hanem hogy **mihez képest** — és hogy a szám, amit nézel, egyáltalán a jó szám-e.

*És ha kiadsz egy élő tippet, néha egyszerűen tévedsz. France 0–2 Spain.*

"""
FIFA World Cup 2026 - Teljes Adatbázis
=======================================
48 csapat, 12 csoport, összes eddigi meccseredmény (csoportkör + kieséses szakasz),
csapatprofilok, játékosstatisztikák, kontextuális tényezők.

Aktuális állapot (2026. július 12.):
- Csoportkör: BEFEJEZVE
- R32 (Nyolcaddöntők): BEFEJEZVE
- R16 (Tizenhatod döntők): BEFEJEZVE
- Negyeddöntők: BEFEJEZVE
- Elődöntők: FOLYAMATBAN (júl. 14-15)
- Döntő: júl. 19
"""

# ==============================================================================
# CSAPATPROFILOK
# ==============================================================================
# Minden csapat részletes profilja a predikciós modellhez.
# Skálák: 0-100 (kivéve ahol jelezve)

TEAMS = {
    # ── CSOPORT A ──────────────────────────────────────────────────────────────
    "Mexico": {
        "group": "A", "confederation": "CONCACAF",
        "fifa_ranking_score": 62, "squad_depth": 68, "star_player_score": 65,
        "coach_quality": 70, "fatigue_factor": 0.92, "injury_factor": 0.95,
        "pressure_index": 75, "tactical_style": "counter",
        "key_players": ["Raúl Jiménez", "Julián Quiñones", "Edson Álvarez"],
        "star_player_goals": 3,  # tornán szerzett gólok
        "notes": "Hazai pálya előny, Azteca erőd; R16-ban kiesett Angliától 2-3",
        "eliminated_round": "R16",
    },
    "South Africa": {
        "group": "A", "confederation": "CAF",
        "fifa_ranking_score": 42, "squad_depth": 45, "star_player_score": 38,
        "coach_quality": 50, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 40, "tactical_style": "defensive",
        "key_players": ["Percy Tau", "Themba Zwane", "Ronwen Williams"],
        "star_player_goals": 0,
        "notes": "Meglepetés: R32-ig jutott",
        "eliminated_round": "R32",
    },
    "South Korea": {
        "group": "A", "confederation": "AFC",
        "fifa_ranking_score": 48, "squad_depth": 55, "star_player_score": 55,
        "coach_quality": 58, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 60, "tactical_style": "high_press",
        "key_players": ["Son Heung-min", "Lee Kang-in", "Kim Min-jae"],
        "star_player_goals": 1,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },
    "Czechia": {
        "group": "A", "confederation": "UEFA",
        "fifa_ranking_score": 40, "squad_depth": 48, "star_player_score": 42,
        "coach_quality": 52, "fatigue_factor": 0.91, "injury_factor": 0.93,
        "pressure_index": 35, "tactical_style": "defensive",
        "key_players": ["Tomáš Souček", "Patrik Schick", "Vladimír Coufal"],
        "star_player_goals": 1,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT B ──────────────────────────────────────────────────────────────
    "Switzerland": {
        "group": "B", "confederation": "UEFA",
        "fifa_ranking_score": 60, "squad_depth": 65, "star_player_score": 58,
        "coach_quality": 68, "fatigue_factor": 0.91, "injury_factor": 0.90,
        "pressure_index": 50, "tactical_style": "defensive",
        "key_players": ["Granit Xhaka", "Xherdan Shaqiri", "Breel Embolo"],
        "star_player_goals": 2,
        "notes": "Negyeddöntőben kiesett Argentínától (Embolo piros lap, h.u. 1-3)",
        "eliminated_round": "QF",
    },
    "Canada": {
        "group": "B", "confederation": "CONCACAF",
        "fifa_ranking_score": 52, "squad_depth": 58, "star_player_score": 55,
        "coach_quality": 62, "fatigue_factor": 0.92, "injury_factor": 0.94,
        "pressure_index": 55, "tactical_style": "high_press",
        "key_players": ["Alphonso Davies", "Jonathan David", "Cyle Larin"],
        "star_player_goals": 4,
        "notes": "R16-ban kiesett Marokkótól 0-3",
        "eliminated_round": "R16",
    },
    "Bosnia & Herzegovina": {
        "group": "B", "confederation": "UEFA",
        "fifa_ranking_score": 38, "squad_depth": 42, "star_player_score": 40,
        "coach_quality": 48, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 30, "tactical_style": "counter",
        "key_players": ["Edin Džeko", "Miralem Pjanić", "Sead Kolašinac"],
        "star_player_goals": 2,
        "notes": "R32-ban kiesett USA-tól 0-2",
        "eliminated_round": "R32",
    },
    "Qatar": {
        "group": "B", "confederation": "AFC",
        "fifa_ranking_score": 28, "squad_depth": 32, "star_player_score": 25,
        "coach_quality": 40, "fatigue_factor": 0.88, "injury_factor": 0.91,
        "pressure_index": 45, "tactical_style": "defensive",
        "key_players": ["Akram Afif", "Almoez Ali", "Hassan Al-Haydos"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT C ──────────────────────────────────────────────────────────────
    "Brazil": {
        "group": "C", "confederation": "CONMEBOL",
        "fifa_ranking_score": 78, "squad_depth": 82, "star_player_score": 80,
        "coach_quality": 75, "fatigue_factor": 0.89, "injury_factor": 0.88,
        "pressure_index": 90, "tactical_style": "possession",
        "key_players": ["Vinicius Jr.", "Neymar", "Rodrygo"],
        "star_player_goals": 3,
        "notes": "R16-ban kiesett Norvégiától 0-2 (Haaland bravúr); Neymar 4 VB-n gólt szerzett",
        "eliminated_round": "R16",
    },
    "Morocco": {
        "group": "C", "confederation": "CAF",
        "fifa_ranking_score": 65, "squad_depth": 68, "star_player_score": 62,
        "coach_quality": 72, "fatigue_factor": 0.91, "injury_factor": 0.93,
        "pressure_index": 65, "tactical_style": "defensive",
        "key_players": ["Achraf Hakimi", "Hakim Ziyech", "Youssef En-Nesyri"],
        "star_player_goals": 5,
        "notes": "Negyeddöntőben kiesett Franciaországtól 0-2",
        "eliminated_round": "QF",
    },
    "Scotland": {
        "group": "C", "confederation": "UEFA",
        "fifa_ranking_score": 38, "squad_depth": 42, "star_player_score": 38,
        "coach_quality": 48, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 40, "tactical_style": "high_press",
        "key_players": ["Andrew Robertson", "Scott McTominay", "Kieran Tierney"],
        "star_player_goals": 1,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },
    "Haiti": {
        "group": "C", "confederation": "CONCACAF",
        "fifa_ranking_score": 22, "squad_depth": 25, "star_player_score": 20,
        "coach_quality": 30, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 25, "tactical_style": "defensive",
        "key_players": ["Frantzdy Pierrot", "Duckens Nazon"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT D ──────────────────────────────────────────────────────────────
    "USA": {
        "group": "D", "confederation": "CONCACAF",
        "fifa_ranking_score": 62, "squad_depth": 68, "star_player_score": 65,
        "coach_quality": 70, "fatigue_factor": 0.92, "injury_factor": 0.91,
        "pressure_index": 80, "tactical_style": "high_press",
        "key_players": ["Christian Pulisic", "Folarin Balogun", "Weston McKennie"],
        "star_player_goals": 4,
        "notes": "R16-ban kiesett Belgiumtól 1-4; Balogun felfüggesztés",
        "eliminated_round": "R16",
    },
    "Australia": {
        "group": "D", "confederation": "AFC",
        "fifa_ranking_score": 45, "squad_depth": 50, "star_player_score": 45,
        "coach_quality": 55, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 45, "tactical_style": "counter",
        "key_players": ["Mathew Ryan", "Aziz Behich", "Mitchell Duke"],
        "star_player_goals": 0,
        "notes": "R32-ban kiesett Egyiptomtól büntetőkkel",
        "eliminated_round": "R32",
    },
    "Paraguay": {
        "group": "D", "confederation": "CONMEBOL",
        "fifa_ranking_score": 42, "squad_depth": 48, "star_player_score": 42,
        "coach_quality": 52, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 40, "tactical_style": "defensive",
        "key_players": ["Miguel Almirón", "Ángel Romero"],
        "star_player_goals": 1,
        "notes": "R16-ban kiesett Franciaországtól 0-1",
        "eliminated_round": "R16",
    },
    "Türkiye": {
        "group": "D", "confederation": "UEFA",
        "fifa_ranking_score": 45, "squad_depth": 50, "star_player_score": 48,
        "coach_quality": 55, "fatigue_factor": 0.91, "injury_factor": 0.92,
        "pressure_index": 50, "tactical_style": "counter",
        "key_players": ["Hakan Çalhanoğlu", "Arda Güler", "Kenan Yıldız"],
        "star_player_goals": 2,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT E ──────────────────────────────────────────────────────────────
    "Germany": {
        "group": "E", "confederation": "UEFA",
        "fifa_ranking_score": 72, "squad_depth": 78, "star_player_score": 72,
        "coach_quality": 75, "fatigue_factor": 0.90, "injury_factor": 0.89,
        "pressure_index": 85, "tactical_style": "high_press",
        "key_players": ["Florian Wirtz", "Jamal Musiala", "Kai Havertz"],
        "star_player_goals": 5,
        "notes": "R32-ban kiesett Paraguaytól büntetőkkel 1-1 (3-4); nem szuperhatalom már",
        "eliminated_round": "R32",
    },
    "Ivory Coast": {
        "group": "E", "confederation": "CAF",
        "fifa_ranking_score": 52, "squad_depth": 55, "star_player_score": 52,
        "coach_quality": 58, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 55, "tactical_style": "counter",
        "key_players": ["Sébastien Haller", "Franck Kessié", "Simon Adingra"],
        "star_player_goals": 2,
        "notes": "R32-ban kiesett Norvégiától 1-2",
        "eliminated_round": "R32",
    },
    "Ecuador": {
        "group": "E", "confederation": "CONMEBOL",
        "fifa_ranking_score": 45, "squad_depth": 48, "star_player_score": 45,
        "coach_quality": 52, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 40, "tactical_style": "counter",
        "key_players": ["Enner Valencia", "Moisés Caicedo"],
        "star_player_goals": 1,
        "notes": "R32-ban kiesett Mexikótól 0-2",
        "eliminated_round": "R32",
    },
    "Curaçao": {
        "group": "E", "confederation": "CONCACAF",
        "fifa_ranking_score": 20, "squad_depth": 22, "star_player_score": 18,
        "coach_quality": 28, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 20, "tactical_style": "defensive",
        "key_players": ["Cuco Martina"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT F ──────────────────────────────────────────────────────────────
    "Netherlands": {
        "group": "F", "confederation": "UEFA",
        "fifa_ranking_score": 72, "squad_depth": 75, "star_player_score": 72,
        "coach_quality": 72, "fatigue_factor": 0.90, "injury_factor": 0.89,
        "pressure_index": 70, "tactical_style": "possession",
        "key_players": ["Cody Gakpo", "Brian Brobbey", "Virgil van Dijk"],
        "star_player_goals": 4,
        "notes": "R32-ban kiesett Marokkótól büntetőkkel 1-1 (2-3)",
        "eliminated_round": "R32",
    },
    "Japan": {
        "group": "F", "confederation": "AFC",
        "fifa_ranking_score": 55, "squad_depth": 60, "star_player_score": 55,
        "coach_quality": 62, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 60, "tactical_style": "high_press",
        "key_players": ["Takumi Minamino", "Ritsu Doan", "Daichi Kamada"],
        "star_player_goals": 3,
        "notes": "R16-ban kiesett Brazíliától 1-2",
        "eliminated_round": "R16",
    },
    "Sweden": {
        "group": "F", "confederation": "UEFA",
        "fifa_ranking_score": 52, "squad_depth": 55, "star_player_score": 52,
        "coach_quality": 58, "fatigue_factor": 0.91, "injury_factor": 0.92,
        "pressure_index": 50, "tactical_style": "counter",
        "key_players": ["Alexander Isak", "Dejan Kulusevski", "Emil Forsberg"],
        "star_player_goals": 3,
        "notes": "R16-ban kiesett Franciaországtól 0-3",
        "eliminated_round": "R16",
    },
    "Tunisia": {
        "group": "F", "confederation": "CAF",
        "fifa_ranking_score": 30, "squad_depth": 32, "star_player_score": 28,
        "coach_quality": 38, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 30, "tactical_style": "defensive",
        "key_players": ["Wahbi Khazri", "Youssef Msakni"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT G ──────────────────────────────────────────────────────────────
    "Belgium": {
        "group": "G", "confederation": "UEFA",
        "fifa_ranking_score": 74, "squad_depth": 78, "star_player_score": 75,
        "coach_quality": 72, "fatigue_factor": 0.90, "injury_factor": 0.85,
        "pressure_index": 75, "tactical_style": "possession",
        "key_players": ["Kevin De Bruyne", "Romelu Lukaku", "Jérémy Doku"],
        "star_player_goals": 3,
        "notes": "Negyeddöntőben kiesett Spanyolországtól 1-2; Courtois sérülés döntő volt",
        "eliminated_round": "QF",
        "key_injury": "Thibaut Courtois (sérülés QF-ben)",
    },
    "Egypt": {
        "group": "G", "confederation": "CAF",
        "fifa_ranking_score": 50, "squad_depth": 52, "star_player_score": 55,
        "coach_quality": 58, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 55, "tactical_style": "counter",
        "key_players": ["Mohamed Salah", "Mostafa Mohamed"],
        "star_player_goals": 3,
        "notes": "Negyeddöntőben kiesett Argentínától 2-3",
        "eliminated_round": "QF",
    },
    "Iran": {
        "group": "G", "confederation": "AFC",
        "fifa_ranking_score": 32, "squad_depth": 35, "star_player_score": 30,
        "coach_quality": 42, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 35, "tactical_style": "defensive",
        "key_players": ["Sardar Azmoun", "Mehdi Taremi"],
        "star_player_goals": 1,
        "notes": "Csoportkörben kiesett (3 döntetlen)",
        "eliminated_round": "group",
    },
    "New Zealand": {
        "group": "G", "confederation": "OFC",
        "fifa_ranking_score": 22, "squad_depth": 25, "star_player_score": 20,
        "coach_quality": 30, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 20, "tactical_style": "defensive",
        "key_players": ["Chris Wood", "Clayton Lewis"],
        "star_player_goals": 1,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT H ──────────────────────────────────────────────────────────────
    "Spain": {
        "group": "H", "confederation": "UEFA",
        "fifa_ranking_score": 88, "squad_depth": 90, "star_player_score": 88,
        "coach_quality": 88, "fatigue_factor": 0.91, "injury_factor": 0.93,
        "pressure_index": 80, "tactical_style": "possession",
        "key_players": ["Lamine Yamal", "Pedri", "Rodri", "Mikel Merino"],
        "star_player_goals": 4,
        "notes": "Elődöntőben: France vs Spain (júl. 14); Merino hős a QF-ben",
        "eliminated_round": None,  # még bent van
        "tournament_goals": 10,
    },
    "Cape Verde": {
        "group": "H", "confederation": "CAF",
        "fifa_ranking_score": 30, "squad_depth": 32, "star_player_score": 28,
        "coach_quality": 38, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 25, "tactical_style": "defensive",
        "key_players": ["Garry Rodrigues", "Ryan Mendes"],
        "star_player_goals": 1,
        "notes": "R32-ban kiesett Argentínától 2-3 h.u.",
        "eliminated_round": "R32",
    },
    "Uruguay": {
        "group": "H", "confederation": "CONMEBOL",
        "fifa_ranking_score": 45, "squad_depth": 48, "star_player_score": 45,
        "coach_quality": 52, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 50, "tactical_style": "defensive",
        "key_players": ["Darwin Núñez", "Federico Valverde", "Luis Suárez"],
        "star_player_goals": 1,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },
    "Saudi Arabia": {
        "group": "H", "confederation": "AFC",
        "fifa_ranking_score": 28, "squad_depth": 30, "star_player_score": 25,
        "coach_quality": 38, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 35, "tactical_style": "defensive",
        "key_players": ["Salem Al-Dawsari", "Mohammed Al-Owais"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT I ──────────────────────────────────────────────────────────────
    "France": {
        "group": "I", "confederation": "UEFA",
        "fifa_ranking_score": 92, "squad_depth": 92, "star_player_score": 95,
        "coach_quality": 90, "fatigue_factor": 0.92, "injury_factor": 0.94,
        "pressure_index": 85, "tactical_style": "counter",
        "key_players": ["Kylian Mbappé", "Ousmane Dembélé", "Antoine Griezmann", "Aurélien Tchouaméni"],
        "star_player_goals": 8,
        "notes": "Elődöntőben: France vs Spain (júl. 14); Mbappé 8 gól, arany cipő verseny",
        "eliminated_round": None,
        "tournament_goals": 12,
    },
    "Norway": {
        "group": "I", "confederation": "UEFA",
        "fifa_ranking_score": 62, "squad_depth": 65, "star_player_score": 82,
        "coach_quality": 65, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 60, "tactical_style": "counter",
        "key_players": ["Erling Haaland", "Martin Ødegaard", "Andreas Schjelderup"],
        "star_player_goals": 7,
        "notes": "Negyeddöntőben kiesett Angliától 1-2 h.u.; Haaland 7 gól de QF-ben gyenge",
        "eliminated_round": "QF",
    },
    "Senegal": {
        "group": "I", "confederation": "CAF",
        "fifa_ranking_score": 48, "squad_depth": 52, "star_player_score": 50,
        "coach_quality": 55, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 50, "tactical_style": "counter",
        "key_players": ["Sadio Mané", "Kalidou Koulibaly", "Idrissa Gueye"],
        "star_player_goals": 5,
        "notes": "R16-ban kiesett Belgiumtól 2-3 h.u.",
        "eliminated_round": "R16",
    },
    "Iraq": {
        "group": "I", "confederation": "AFC",
        "fifa_ranking_score": 25, "squad_depth": 28, "star_player_score": 22,
        "coach_quality": 32, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 25, "tactical_style": "defensive",
        "key_players": ["Mohanad Ali", "Amjad Attwan"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT J ──────────────────────────────────────────────────────────────
    "Argentina": {
        "group": "J", "confederation": "CONMEBOL",
        "fifa_ranking_score": 90, "squad_depth": 88, "star_player_score": 95,
        "coach_quality": 88, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 90, "tactical_style": "counter",
        "key_players": ["Lionel Messi", "Julián Álvarez", "Rodrigo De Paul", "Enzo Fernández"],
        "star_player_goals": 8,
        "notes": "Elődöntőben: England vs Argentina (júl. 15); Messi 8 gól, Álvarez visszatért",
        "eliminated_round": None,
        "tournament_goals": 14,
    },
    "Austria": {
        "group": "J", "confederation": "UEFA",
        "fifa_ranking_score": 48, "squad_depth": 52, "star_player_score": 48,
        "coach_quality": 55, "fatigue_factor": 0.90, "injury_factor": 0.92,
        "pressure_index": 45, "tactical_style": "high_press",
        "key_players": ["Marcel Sabitzer", "David Alaba", "Marko Arnautovic"],
        "star_player_goals": 2,
        "notes": "R32-ban kiesett Spanyolországtól 0-3",
        "eliminated_round": "R32",
    },
    "Algeria": {
        "group": "J", "confederation": "CAF",
        "fifa_ranking_score": 40, "squad_depth": 42, "star_player_score": 38,
        "coach_quality": 48, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 40, "tactical_style": "counter",
        "key_players": ["Riyad Mahrez", "Islam Slimani"],
        "star_player_goals": 2,
        "notes": "R32-ban kiesett Svájctól 0-2",
        "eliminated_round": "R32",
    },
    "Jordan": {
        "group": "J", "confederation": "AFC",
        "fifa_ranking_score": 25, "squad_depth": 28, "star_player_score": 22,
        "coach_quality": 32, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 25, "tactical_style": "defensive",
        "key_players": ["Mousa Al-Taamari", "Baha' Faisal"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT K ──────────────────────────────────────────────────────────────
    "Colombia": {
        "group": "K", "confederation": "CONMEBOL",
        "fifa_ranking_score": 62, "squad_depth": 65, "star_player_score": 62,
        "coach_quality": 68, "fatigue_factor": 0.91, "injury_factor": 0.93,
        "pressure_index": 60, "tactical_style": "counter",
        "key_players": ["James Rodríguez", "Luis Díaz", "Jhon Córdoba"],
        "star_player_goals": 2,
        "notes": "R16-ban kiesett Svájctól büntetőkkel 0-0 (3-4)",
        "eliminated_round": "R16",
    },
    "Portugal": {
        "group": "K", "confederation": "UEFA",
        "fifa_ranking_score": 80, "squad_depth": 82, "star_player_score": 82,
        "coach_quality": 78, "fatigue_factor": 0.90, "injury_factor": 0.88,
        "pressure_index": 80, "tactical_style": "counter",
        "key_players": ["Cristiano Ronaldo", "Bruno Fernandes", "Rafael Leão"],
        "star_player_goals": 4,
        "notes": "R16-ban kiesett Spanyolországtól 0-1; Ronaldo VB karrierje véget ért",
        "eliminated_round": "R16",
        "key_injury": "Diogo Jota (elhunyt - tiszteletadás)",
    },
    "DR Congo": {
        "group": "K", "confederation": "CAF",
        "fifa_ranking_score": 38, "squad_depth": 40, "star_player_score": 38,
        "coach_quality": 45, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 35, "tactical_style": "counter",
        "key_players": ["Cédric Bakambu", "Chancel Mbemba"],
        "star_player_goals": 2,
        "notes": "R32-ban kiesett Angliától 1-2",
        "eliminated_round": "R32",
    },
    "Uzbekistan": {
        "group": "K", "confederation": "AFC",
        "fifa_ranking_score": 25, "squad_depth": 28, "star_player_score": 22,
        "coach_quality": 32, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 20, "tactical_style": "defensive",
        "key_players": ["Eldor Shomurodov", "Jasur Yaxshiboyev"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },

    # ── CSOPORT L ──────────────────────────────────────────────────────────────
    "England": {
        "group": "L", "confederation": "UEFA",
        "fifa_ranking_score": 86, "squad_depth": 88, "star_player_score": 88,
        "coach_quality": 82, "fatigue_factor": 0.91, "injury_factor": 0.92,
        "pressure_index": 88, "tactical_style": "high_press",
        "key_players": ["Jude Bellingham", "Harry Kane", "Phil Foden", "Bukayo Saka"],
        "star_player_goals": 6,
        "notes": "Elődöntőben: England vs Argentina (júl. 15); Bellingham hős Mexikó és Norvégia ellen",
        "eliminated_round": None,
        "tournament_goals": 13,
    },
    "Croatia": {
        "group": "L", "confederation": "UEFA",
        "fifa_ranking_score": 52, "squad_depth": 55, "star_player_score": 52,
        "coach_quality": 60, "fatigue_factor": 0.90, "injury_factor": 0.91,
        "pressure_index": 55, "tactical_style": "possession",
        "key_players": ["Luka Modrić", "Ivan Perišić", "Mateo Kovačić"],
        "star_player_goals": 2,
        "notes": "R32-ban kiesett Portugáliától 1-2",
        "eliminated_round": "R32",
    },
    "Ghana": {
        "group": "L", "confederation": "CAF",
        "fifa_ranking_score": 38, "squad_depth": 40, "star_player_score": 38,
        "coach_quality": 45, "fatigue_factor": 0.89, "injury_factor": 0.91,
        "pressure_index": 40, "tactical_style": "counter",
        "key_players": ["Jordan Ayew", "Thomas Partey", "Mohammed Kudus"],
        "star_player_goals": 1,
        "notes": "R32-ban kiesett Kolumbiától 0-1",
        "eliminated_round": "R32",
    },
    "Panama": {
        "group": "L", "confederation": "CONCACAF",
        "fifa_ranking_score": 22, "squad_depth": 25, "star_player_score": 20,
        "coach_quality": 30, "fatigue_factor": 0.88, "injury_factor": 0.90,
        "pressure_index": 20, "tactical_style": "defensive",
        "key_players": ["Rolando Blackburn", "Cecilio Waterman"],
        "star_player_goals": 0,
        "notes": "Csoportkörben kiesett",
        "eliminated_round": "group",
    },
}

# ==============================================================================
# KONTEXTUÁLIS TÉNYEZŐK
# ==============================================================================

CONTEXTUAL_FACTORS = {
    # Utazási fáradtság konföderáció szerint (szorzó)
    "travel_impact": {
        "UEFA": 0.97,
        "CONMEBOL": 0.94,
        "CONCACAF": 0.99,  # hazai pálya előny
        "CAF": 0.91,
        "AFC": 0.88,
        "OFC": 0.85,
    },
    # Torna-tapasztalat szorzó
    "tournament_experience": {
        "France": 1.05, "Argentina": 1.05, "Brazil": 1.04,
        "Spain": 1.04, "Germany": 1.03, "England": 1.02,
        "Portugal": 1.03, "Netherlands": 1.02, "Belgium": 1.02,
        "Norway": 1.01, "Mexico": 1.02, "USA": 1.01,
        "default": 0.98,
    },
    # Hőség hatás (USA nyár, júniusi meccsek)
    "heat_impact": {
        "CAF": 1.03,  # afrikai csapatok előnye
        "CONCACAF": 1.02,
        "AFC": 1.01,
        "UEFA": 0.97,
        "CONMEBOL": 0.99,
        "OFC": 0.98,
    },
    # Hazai pálya hatás
    "home_advantage": {
        "USA": 1.04, "Mexico": 1.05, "Canada": 1.03,
    },
}

MOMENTUM_WEIGHTS = {
    "win_streak_bonus": 0.15,
    "clean_sheet_bonus": 0.10,
    "extra_time_penalty": -0.08,
    "penalty_shootout_penalty": -0.05,
}

# ==============================================================================
# CSOPORTKÖR EREDMÉNYEK (TELJES)
# ==============================================================================

GROUP_STAGE_RESULTS = [
    # ── CSOPORT A ──
    {"match_id": "A1", "group": "A", "round": 1, "date": "2026-06-11",
     "home": "Mexico", "away": "South Africa", "home_goals": 2, "away_goals": 0},
    {"match_id": "A2", "group": "A", "round": 1, "date": "2026-06-11",
     "home": "South Korea", "away": "Czechia", "home_goals": 2, "away_goals": 1},
    {"match_id": "A3", "group": "A", "round": 2, "date": "2026-06-18",
     "home": "Czechia", "away": "South Africa", "home_goals": 1, "away_goals": 1},
    {"match_id": "A4", "group": "A", "round": 2, "date": "2026-06-18",
     "home": "Mexico", "away": "South Korea", "home_goals": 1, "away_goals": 0},
    {"match_id": "A5", "group": "A", "round": 3, "date": "2026-06-24",
     "home": "Mexico", "away": "Czechia", "home_goals": 3, "away_goals": 0},
    {"match_id": "A6", "group": "A", "round": 3, "date": "2026-06-24",
     "home": "South Africa", "away": "South Korea", "home_goals": 1, "away_goals": 0},

    # ── CSOPORT B ──
    {"match_id": "B1", "group": "B", "round": 1, "date": "2026-06-12",
     "home": "Canada", "away": "Bosnia & Herzegovina", "home_goals": 1, "away_goals": 1},
    {"match_id": "B2", "group": "B", "round": 1, "date": "2026-06-13",
     "home": "Switzerland", "away": "Qatar", "home_goals": 1, "away_goals": 1},
    {"match_id": "B3", "group": "B", "round": 2, "date": "2026-06-18",
     "home": "Switzerland", "away": "Bosnia & Herzegovina", "home_goals": 4, "away_goals": 1},
    {"match_id": "B4", "group": "B", "round": 2, "date": "2026-06-18",
     "home": "Canada", "away": "Qatar", "home_goals": 6, "away_goals": 0},
    {"match_id": "B5", "group": "B", "round": 3, "date": "2026-06-24",
     "home": "Switzerland", "away": "Canada", "home_goals": 3, "away_goals": 1},
    {"match_id": "B6", "group": "B", "round": 3, "date": "2026-06-24",
     "home": "Bosnia & Herzegovina", "away": "Qatar", "home_goals": 3, "away_goals": 1},

    # ── CSOPORT C ──
    {"match_id": "C1", "group": "C", "round": 1, "date": "2026-06-13",
     "home": "Brazil", "away": "Morocco", "home_goals": 1, "away_goals": 1},
    {"match_id": "C2", "group": "C", "round": 1, "date": "2026-06-13",
     "home": "Scotland", "away": "Haiti", "home_goals": 1, "away_goals": 0},
    {"match_id": "C3", "group": "C", "round": 2, "date": "2026-06-19",
     "home": "Scotland", "away": "Morocco", "home_goals": 0, "away_goals": 1},
    {"match_id": "C4", "group": "C", "round": 2, "date": "2026-06-19",
     "home": "Brazil", "away": "Haiti", "home_goals": 3, "away_goals": 0},
    {"match_id": "C5", "group": "C", "round": 3, "date": "2026-06-24",
     "home": "Scotland", "away": "Brazil", "home_goals": 0, "away_goals": 3},
    {"match_id": "C6", "group": "C", "round": 3, "date": "2026-06-24",
     "home": "Morocco", "away": "Haiti", "home_goals": 4, "away_goals": 2},

    # ── CSOPORT D ──
    {"match_id": "D1", "group": "D", "round": 1, "date": "2026-06-12",
     "home": "USA", "away": "Paraguay", "home_goals": 4, "away_goals": 1},
    {"match_id": "D2", "group": "D", "round": 1, "date": "2026-06-13",
     "home": "Australia", "away": "Türkiye", "home_goals": 2, "away_goals": 0},
    {"match_id": "D3", "group": "D", "round": 2, "date": "2026-06-19",
     "home": "USA", "away": "Australia", "home_goals": 2, "away_goals": 0},
    {"match_id": "D4", "group": "D", "round": 2, "date": "2026-06-19",
     "home": "Türkiye", "away": "Paraguay", "home_goals": 0, "away_goals": 1},
    {"match_id": "D5", "group": "D", "round": 3, "date": "2026-06-25",
     "home": "Türkiye", "away": "USA", "home_goals": 3, "away_goals": 2},
    {"match_id": "D6", "group": "D", "round": 3, "date": "2026-06-25",
     "home": "Paraguay", "away": "Australia", "home_goals": 0, "away_goals": 0},

    # ── CSOPORT E ──
    {"match_id": "E1", "group": "E", "round": 1, "date": "2026-06-14",
     "home": "Germany", "away": "Curaçao", "home_goals": 7, "away_goals": 1},
    {"match_id": "E2", "group": "E", "round": 1, "date": "2026-06-14",
     "home": "Ivory Coast", "away": "Ecuador", "home_goals": 1, "away_goals": 0},
    {"match_id": "E3", "group": "E", "round": 2, "date": "2026-06-20",
     "home": "Germany", "away": "Ivory Coast", "home_goals": 2, "away_goals": 1},
    {"match_id": "E4", "group": "E", "round": 2, "date": "2026-06-20",
     "home": "Ecuador", "away": "Curaçao", "home_goals": 0, "away_goals": 0},
    {"match_id": "E5", "group": "E", "round": 3, "date": "2026-06-25",
     "home": "Curaçao", "away": "Ivory Coast", "home_goals": 0, "away_goals": 2},
    {"match_id": "E6", "group": "E", "round": 3, "date": "2026-06-25",
     "home": "Ecuador", "away": "Germany", "home_goals": 2, "away_goals": 1},

    # ── CSOPORT F ──
    {"match_id": "F1", "group": "F", "round": 1, "date": "2026-06-14",
     "home": "Netherlands", "away": "Japan", "home_goals": 2, "away_goals": 2},
    {"match_id": "F2", "group": "F", "round": 1, "date": "2026-06-14",
     "home": "Sweden", "away": "Tunisia", "home_goals": 5, "away_goals": 1},
    {"match_id": "F3", "group": "F", "round": 2, "date": "2026-06-20",
     "home": "Netherlands", "away": "Sweden", "home_goals": 5, "away_goals": 1},
    {"match_id": "F4", "group": "F", "round": 2, "date": "2026-06-20",
     "home": "Japan", "away": "Tunisia", "home_goals": 4, "away_goals": 0},
    {"match_id": "F5", "group": "F", "round": 3, "date": "2026-06-25",
     "home": "Japan", "away": "Sweden", "home_goals": 1, "away_goals": 1},
    {"match_id": "F6", "group": "F", "round": 3, "date": "2026-06-25",
     "home": "Netherlands", "away": "Tunisia", "home_goals": 3, "away_goals": 1},

    # ── CSOPORT G ──
    {"match_id": "G1", "group": "G", "round": 1, "date": "2026-06-15",
     "home": "Belgium", "away": "Egypt", "home_goals": 1, "away_goals": 1},
    {"match_id": "G2", "group": "G", "round": 1, "date": "2026-06-15",
     "home": "Iran", "away": "New Zealand", "home_goals": 2, "away_goals": 2},
    {"match_id": "G3", "group": "G", "round": 2, "date": "2026-06-21",
     "home": "Belgium", "away": "Iran", "home_goals": 0, "away_goals": 0},
    {"match_id": "G4", "group": "G", "round": 2, "date": "2026-06-21",
     "home": "Egypt", "away": "New Zealand", "home_goals": 3, "away_goals": 1},
    {"match_id": "G5", "group": "G", "round": 3, "date": "2026-06-26",
     "home": "Egypt", "away": "Iran", "home_goals": 1, "away_goals": 1},
    {"match_id": "G6", "group": "G", "round": 3, "date": "2026-06-26",
     "home": "Belgium", "away": "New Zealand", "home_goals": 5, "away_goals": 1},

    # ── CSOPORT H ──
    {"match_id": "H1", "group": "H", "round": 1, "date": "2026-06-15",
     "home": "Spain", "away": "Cape Verde", "home_goals": 0, "away_goals": 0},
    {"match_id": "H2", "group": "H", "round": 1, "date": "2026-06-15",
     "home": "Saudi Arabia", "away": "Uruguay", "home_goals": 1, "away_goals": 1},
    {"match_id": "H3", "group": "H", "round": 2, "date": "2026-06-21",
     "home": "Spain", "away": "Saudi Arabia", "home_goals": 4, "away_goals": 0},
    {"match_id": "H4", "group": "H", "round": 2, "date": "2026-06-21",
     "home": "Uruguay", "away": "Cape Verde", "home_goals": 2, "away_goals": 2},
    {"match_id": "H5", "group": "H", "round": 3, "date": "2026-06-26",
     "home": "Cape Verde", "away": "Saudi Arabia", "home_goals": 0, "away_goals": 0},
    {"match_id": "H6", "group": "H", "round": 3, "date": "2026-06-26",
     "home": "Spain", "away": "Uruguay", "home_goals": 1, "away_goals": 0},

    # ── CSOPORT I ──
    {"match_id": "I1", "group": "I", "round": 1, "date": "2026-06-16",
     "home": "France", "away": "Senegal", "home_goals": 3, "away_goals": 1},
    {"match_id": "I2", "group": "I", "round": 1, "date": "2026-06-16",
     "home": "Norway", "away": "Iraq", "home_goals": 4, "away_goals": 1},
    {"match_id": "I3", "group": "I", "round": 2, "date": "2026-06-22",
     "home": "France", "away": "Iraq", "home_goals": 3, "away_goals": 0},
    {"match_id": "I4", "group": "I", "round": 2, "date": "2026-06-22",
     "home": "Norway", "away": "Senegal", "home_goals": 3, "away_goals": 2},
    {"match_id": "I5", "group": "I", "round": 3, "date": "2026-06-26",
     "home": "France", "away": "Norway", "home_goals": 4, "away_goals": 1},
    {"match_id": "I6", "group": "I", "round": 3, "date": "2026-06-26",
     "home": "Senegal", "away": "Iraq", "home_goals": 5, "away_goals": 0},

    # ── CSOPORT J ──
    {"match_id": "J1", "group": "J", "round": 1, "date": "2026-06-16",
     "home": "Argentina", "away": "Algeria", "home_goals": 3, "away_goals": 0},
    {"match_id": "J2", "group": "J", "round": 1, "date": "2026-06-16",
     "home": "Austria", "away": "Jordan", "home_goals": 3, "away_goals": 1},
    {"match_id": "J3", "group": "J", "round": 2, "date": "2026-06-22",
     "home": "Argentina", "away": "Austria", "home_goals": 2, "away_goals": 0},
    {"match_id": "J4", "group": "J", "round": 2, "date": "2026-06-22",
     "home": "Jordan", "away": "Algeria", "home_goals": 1, "away_goals": 2},
    {"match_id": "J5", "group": "J", "round": 3, "date": "2026-06-27",
     "home": "Argentina", "away": "Jordan", "home_goals": 3, "away_goals": 1},
    {"match_id": "J6", "group": "J", "round": 3, "date": "2026-06-27",
     "home": "Austria", "away": "Algeria", "home_goals": 3, "away_goals": 3},

    # ── CSOPORT K ──
    {"match_id": "K1", "group": "K", "round": 1, "date": "2026-06-17",
     "home": "Portugal", "away": "DR Congo", "home_goals": 1, "away_goals": 1},
    {"match_id": "K2", "group": "K", "round": 1, "date": "2026-06-17",
     "home": "Uzbekistan", "away": "Colombia", "home_goals": 1, "away_goals": 3},
    {"match_id": "K3", "group": "K", "round": 2, "date": "2026-06-23",
     "home": "Portugal", "away": "Uzbekistan", "home_goals": 5, "away_goals": 0},
    {"match_id": "K4", "group": "K", "round": 2, "date": "2026-06-23",
     "home": "Colombia", "away": "DR Congo", "home_goals": 1, "away_goals": 0},
    {"match_id": "K5", "group": "K", "round": 3, "date": "2026-06-27",
     "home": "Colombia", "away": "Portugal", "home_goals": 0, "away_goals": 0},
    {"match_id": "K6", "group": "K", "round": 3, "date": "2026-06-27",
     "home": "DR Congo", "away": "Uzbekistan", "home_goals": 3, "away_goals": 1},

    # ── CSOPORT L ──
    {"match_id": "L1", "group": "L", "round": 1, "date": "2026-06-17",
     "home": "England", "away": "Croatia", "home_goals": 4, "away_goals": 2},
    {"match_id": "L2", "group": "L", "round": 1, "date": "2026-06-17",
     "home": "Ghana", "away": "Panama", "home_goals": 1, "away_goals": 0},
    {"match_id": "L3", "group": "L", "round": 2, "date": "2026-06-23",
     "home": "England", "away": "Ghana", "home_goals": 0, "away_goals": 0},
    {"match_id": "L4", "group": "L", "round": 2, "date": "2026-06-23",
     "home": "Panama", "away": "Croatia", "home_goals": 0, "away_goals": 1},
    {"match_id": "L5", "group": "L", "round": 3, "date": "2026-06-27",
     "home": "England", "away": "Panama", "home_goals": 2, "away_goals": 0},
    {"match_id": "L6", "group": "L", "round": 3, "date": "2026-06-27",
     "home": "Croatia", "away": "Ghana", "home_goals": 2, "away_goals": 1},
]

# ==============================================================================
# KIESÉSES SZAKASZ EREDMÉNYEK
# ==============================================================================

KNOCKOUT_RESULTS = [
    # ── R32 (Nyolcaddöntők, jún. 28 - júl. 1) ──
    {"match_id": "R32_1", "round": "R32", "date": "2026-06-28",
     "home": "South Africa", "away": "Canada", "home_goals": 0, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "Canada"},
    {"match_id": "R32_2", "round": "R32", "date": "2026-06-29",
     "home": "Brazil", "away": "Japan", "home_goals": 2, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "Brazil"},
    {"match_id": "R32_3", "round": "R32", "date": "2026-06-29",
     "home": "Germany", "away": "Paraguay", "home_goals": 1, "away_goals": 1,
     "extra_time": True, "penalties": True, "winner": "Paraguay",
     "pen_home": 3, "pen_away": 4},
    {"match_id": "R32_4", "round": "R32", "date": "2026-06-29",
     "home": "Netherlands", "away": "Morocco", "home_goals": 1, "away_goals": 1,
     "extra_time": True, "penalties": True, "winner": "Morocco",
     "pen_home": 2, "pen_away": 3},
    {"match_id": "R32_5", "round": "R32", "date": "2026-06-30",
     "home": "Ivory Coast", "away": "Norway", "home_goals": 1, "away_goals": 2,
     "extra_time": False, "penalties": False, "winner": "Norway"},
    {"match_id": "R32_6", "round": "R32", "date": "2026-06-30",
     "home": "France", "away": "Sweden", "home_goals": 3, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "France"},
    {"match_id": "R32_7", "round": "R32", "date": "2026-06-30",
     "home": "Mexico", "away": "Ecuador", "home_goals": 2, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "Mexico"},
    {"match_id": "R32_8", "round": "R32", "date": "2026-07-01",
     "home": "England", "away": "DR Congo", "home_goals": 2, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "England"},
    {"match_id": "R32_9", "round": "R32", "date": "2026-07-01",
     "home": "Belgium", "away": "Senegal", "home_goals": 3, "away_goals": 2,
     "extra_time": True, "penalties": False, "winner": "Belgium"},
    {"match_id": "R32_10", "round": "R32", "date": "2026-07-01",
     "home": "USA", "away": "Bosnia & Herzegovina", "home_goals": 2, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "USA"},
    {"match_id": "R32_11", "round": "R32", "date": "2026-07-02",
     "home": "Spain", "away": "Austria", "home_goals": 3, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "Spain"},
    {"match_id": "R32_12", "round": "R32", "date": "2026-07-02",
     "home": "Portugal", "away": "Croatia", "home_goals": 2, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "Portugal"},
    {"match_id": "R32_13", "round": "R32", "date": "2026-07-02",
     "home": "Switzerland", "away": "Algeria", "home_goals": 2, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "Switzerland"},
    {"match_id": "R32_14", "round": "R32", "date": "2026-07-03",
     "home": "Australia", "away": "Egypt", "home_goals": 1, "away_goals": 1,
     "extra_time": True, "penalties": True, "winner": "Egypt",
     "pen_home": 2, "pen_away": 4},
    {"match_id": "R32_15", "round": "R32", "date": "2026-07-03",
     "home": "Argentina", "away": "Cape Verde", "home_goals": 3, "away_goals": 2,
     "extra_time": True, "penalties": False, "winner": "Argentina"},
    {"match_id": "R32_16", "round": "R32", "date": "2026-07-03",
     "home": "Colombia", "away": "Ghana", "home_goals": 1, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "Colombia"},

    # ── R16 (Tizenhatod döntők, júl. 4-6) ──
    {"match_id": "R16_1", "round": "R16", "date": "2026-07-04",
     "home": "Morocco", "away": "Canada", "home_goals": 3, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "Morocco"},
    {"match_id": "R16_2", "round": "R16", "date": "2026-07-04",
     "home": "Paraguay", "away": "France", "home_goals": 0, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "France"},
    {"match_id": "R16_3", "round": "R16", "date": "2026-07-05",
     "home": "Brazil", "away": "Norway", "home_goals": 1, "away_goals": 2,
     "extra_time": False, "penalties": False, "winner": "Norway",
     "source": "official"},  # javítva: hivatalos adat 1-2 (korábban tévesen 0-2)
    {"match_id": "R16_4", "round": "R16", "date": "2026-07-05",
     "home": "Mexico", "away": "England", "home_goals": 2, "away_goals": 3,
     "extra_time": False, "penalties": False, "winner": "England"},
    {"match_id": "R16_5", "round": "R16", "date": "2026-07-06",
     "home": "Portugal", "away": "Spain", "home_goals": 0, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "Spain"},
    {"match_id": "R16_6", "round": "R16", "date": "2026-07-06",
     "home": "USA", "away": "Belgium", "home_goals": 1, "away_goals": 4,
     "extra_time": False, "penalties": False, "winner": "Belgium"},
    {"match_id": "R16_7", "round": "R16", "date": "2026-07-07",
     "home": "Argentina", "away": "Egypt", "home_goals": 3, "away_goals": 2,
     "extra_time": False, "penalties": False, "winner": "Argentina"},
    {"match_id": "R16_8", "round": "R16", "date": "2026-07-07",
     "home": "Switzerland", "away": "Colombia", "home_goals": 0, "away_goals": 0,
     "extra_time": True, "penalties": True, "winner": "Switzerland",
     "pen_home": 4, "pen_away": 3},

    # ── QF (Negyeddöntők, júl. 9-11) ──
    {"match_id": "QF_1", "round": "QF", "date": "2026-07-09",
     "home": "France", "away": "Morocco", "home_goals": 2, "away_goals": 0,
     "extra_time": False, "penalties": False, "winner": "France"},
    {"match_id": "QF_2", "round": "QF", "date": "2026-07-10",
     "home": "Spain", "away": "Belgium", "home_goals": 2, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "Spain"},
    {"match_id": "QF_3", "round": "QF", "date": "2026-07-11",
     "home": "Norway", "away": "England", "home_goals": 1, "away_goals": 2,
     "extra_time": True, "penalties": False, "winner": "England"},
    {"match_id": "QF_4", "round": "QF", "date": "2026-07-11",
     "home": "Argentina", "away": "Switzerland", "home_goals": 3, "away_goals": 1,
     "extra_time": False, "penalties": False, "winner": "Argentina",
     "source": "official"},  # javítva: hivatalos adat ARG 3-1 SUI rendes játékidőben (korábban tévesen SUI 0-3 hosszabbítással)

    # ── SF (Elődöntők) ──
    {"match_id": "SF_1", "round": "SF", "date": "2026-07-14",
     "home": "France", "away": "Spain", "home_goals": 0, "away_goals": 2,
     "extra_time": False, "penalties": False, "winner": "Spain",
     "source": "official",
     # Forrás: FIFA match report, Reuters ("Spain choke life out of France"),
     # Al Jazeera live (2026-07-14). Gólok: Oyarzabal 22' (11-es), Pedro Porro 58'.
     # A modell FRANCE-t tippelte 73,7%-ra -> a rendszer TÉVEDETT (piros).
     "goals": ["Oyarzabal 22' (pen)", "Pedro Porro 58'"]},
    # ── SF_2 (England-Argentina, júl. 15) - MÉG NEM JÁTSZÓDOTT LE ──
    # {"match_id": "SF_2", "round": "SF", "date": "2026-07-15",
    #  "home": "England", "away": "Argentina", ...},

    # ── FINAL (Döntő, júl. 19) - MÉG NEM JÁTSZÓDOTT LE ──
    # {"match_id": "FINAL", "round": "FINAL", "date": "2026-07-19", ...},
]

# ==============================================================================
# ELŐDÖNTŐ PÁROSÍTÁSOK (fix)
# ==============================================================================
SEMIFINAL_MATCHUPS = {
    "SF_1": {"home": "France", "away": "Spain", "date": "2026-07-14",
             "venue": "AT&T Stadium, Arlington (Dallas)"},
    "SF_2": {"home": "England", "away": "Argentina", "date": "2026-07-15",
             "venue": "Mercedes-Benz Stadium, Atlanta"},
}

# ==============================================================================
# VALÓS VÉGEREDMÉNY (validációhoz - majd frissítendő)
# ==============================================================================
ACTUAL_TOP5 = []  # Még nem ismert - júl. 19 után
ACTUAL_WINNER = None  # Még nem ismert

# A negyeddöntők alapján ismert top 8:
ACTUAL_TOP8_CONFIRMED = ["France", "Spain", "England", "Argentina",
                          "Norway", "Switzerland", "Belgium", "Morocco"]

# ==============================================================================
# SEGÉDFÜGGVÉNYEK
# ==============================================================================

def get_all_known_results():
    """Visszaadja az összes eddig lejátszott meccs eredményét."""
    return GROUP_STAGE_RESULTS + KNOCKOUT_RESULTS


def get_remaining_matches():
    """Visszaadja a még le nem játszott meccseket."""
    played_ids = {r["match_id"] for r in get_all_known_results()}
    remaining = []
    for match_id, info in SEMIFINAL_MATCHUPS.items():
        if match_id not in played_ids:
            remaining.append({"match_id": match_id, **info})
    # Döntő
    if "FINAL" not in played_ids:
        remaining.append({"match_id": "FINAL", "round": "FINAL",
                          "date": "2026-07-19",
                          "venue": "MetLife Stadium, East Rutherford (New York)"})
    return remaining


def get_current_stage():
    """Meghatározza az aktuális torna-szakaszt."""
    played_ids = {r["match_id"] for r in get_all_known_results()}
    if "FINAL" in played_ids:
        return "COMPLETED"
    elif any(mid in played_ids for mid in ["SF_1", "SF_2"]):
        return "FINAL"
    elif any(mid in played_ids for mid in ["QF_1", "QF_2", "QF_3", "QF_4"]):
        return "SEMIFINAL"
    elif any(mid.startswith("R16") for mid in played_ids):
        return "QUARTERFINAL"
    elif any(mid.startswith("R32") for mid in played_ids):
        return "R16"
    elif any(r.get("round") in [1, 2, 3] for r in GROUP_STAGE_RESULTS if r["match_id"] in played_ids):
        return "GROUP_STAGE"
    return "PRE_TOURNAMENT"

#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# WC2026 Predikció — Termux telepítő (egyszeri futtatás)
# Használat: a projekt mappájából:  bash termux_setup.sh
# ==============================================================================
set -e

echo "── WC2026 Termux telepítő ──"

# 1) Csomagok
echo "[1/4] Termux csomagok…"
pkg update -y
pkg install -y python termux-tools

# 2) Python függőségek — először a normál út, ha a pydantic v2 Rust-magja
#    miatt elhasal, pydantic v1-es (tiszta Python) fallback
echo "[2/4] Python csomagok (fastapi + uvicorn)…"
if pip install --no-input fastapi uvicorn 2>/dev/null; then
    echo "    OK (pydantic v2)"
else
    echo "    pydantic v2 fordítás elakadt — fallback tiszta-Python pydantic v1-re"
    pip install --no-input "fastapi==0.99.1" "pydantic<2" "uvicorn==0.22.0"
    echo "    OK (pydantic v1 fallback)"
fi

# 3) Ellenőrzés: a szerver betölthető-e
echo "[3/4] Szerver-önteszt…"
python - << 'EOF'
import server_wc2026
print("    OK — a szerver modul betölt, build:", server_wc2026.KV_BUILD)
EOF

# 4) Opcionális API-kulcs a hivatalos eredmény-letöltéshez
echo "[4/4] API-kulcs (opcionális)"
if [ -z "$FOOTBALL_DATA_API_KEY" ]; then
    echo "    Nincs FOOTBALL_DATA_API_KEY beállítva."
    echo "    Ingyenes kulcs: https://www.football-data.org/client/register"
    printf "    Add meg most (Enter = kihagyás): "
    read -r KEY
    if [ -n "$KEY" ]; then
        echo "export FOOTBALL_DATA_API_KEY='$KEY'" >> "$HOME/.bashrc"
        echo "    Mentve a ~/.bashrc-be (új terminálban él)."
    else
        echo "    Kihagyva — a 🔄 frissítés a beépített cache-ből ellenőriz."
    fi
else
    echo "    Kulcs már beállítva."
fi

echo ""
echo "── KÉSZ ──"
echo "Indítás:            bash termux_start.sh"
echo "Automatikus indítás bootkor: lásd a termux_boot_wc2026.sh fejlécét"

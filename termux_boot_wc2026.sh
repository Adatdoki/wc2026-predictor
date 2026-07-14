#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# WC2026 Predikció — automatikus indítás telefon-bootkor (Termux:Boot)
#
# Beüzemelés (a videómegosztós mintád szerint):
#   1. Termux:Boot app telepítése (F-Droid), egyszer megnyitni
#   2. mkdir -p ~/.termux/boot
#   3. cp termux_boot_wc2026.sh ~/.termux/boot/
#   4. chmod +x ~/.termux/boot/termux_boot_wc2026.sh
#   5. Ha a projekt nem a ~/wc2026_predictor mappában van, írd át a
#      PROJECT_DIR értékét alább.
#
# Napló: ~/wc2026_boot.log
# ==============================================================================
PROJECT_DIR="$HOME/wc2026_predictor"
PORT=8026

termux-wake-lock
cd "$PROJECT_DIR" || exit 1
nohup python server_wc2026.py --host 0.0.0.0 --port "$PORT" \
    > "$HOME/wc2026_boot.log" 2>&1 &

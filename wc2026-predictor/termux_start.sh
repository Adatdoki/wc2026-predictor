#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# WC2026 Predikció — indítás Termuxon
# Használat: a projekt mappájából:  bash termux_start.sh [port]
# ==============================================================================
PORT="${1:-8026}"
cd "$(dirname "$0")"

# Ébren tartás, hogy az Android ne altassa el a szervert
command -v termux-wake-lock >/dev/null && termux-wake-lock

# Helyi IP kiírása, hogy a wifi-n más eszközről is elérhető legyen
LOCAL_IP=$(ip -4 addr show 2>/dev/null | grep -oP '(?<=inet )192\.168\.[0-9.]+|(?<=inet )10\.[0-9.]+' | head -1)

echo "── WC2026 Predikció ──"
echo "  Telefonon:      http://localhost:$PORT"
[ -n "$LOCAL_IP" ] && echo "  Wifi-ről:       http://$LOCAL_IP:$PORT"
echo "  Leállítás: Ctrl+C  (utána: termux-wake-unlock)"
echo ""

python server_wc2026.py --host 0.0.0.0 --port "$PORT"

command -v termux-wake-unlock >/dev/null && termux-wake-unlock

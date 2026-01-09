from __future__ import annotations

import time
import threading
import importlib
from collections import deque
from flask import Flask, request, jsonify


# =========================
# CONFIG
# =========================
# ⚠️ Mets ici le NOM de ton fichier série SANS ".py"
# Exemple : si ton fichier s'appelle "arduino.py" -> "arduino"
#          si ton fichier s'appelle "arduino_serial.py" -> "arduino_serial"
SERIAL_MODULE_NAME = "arduino"

LOCAL_TOKEN = "local-change-moi-12345"   # doit matcher ROVER_LOCAL_TOKEN côté ai_rover
HOST = "127.0.0.1"
PORT = 5055

# Buffer télémétrie (optionnel)
_last_lines = deque(maxlen=50)
_last_lock = threading.Lock()


# =========================
# IMPORT MODULE SERIE
# =========================
arduino = importlib.import_module(SERIAL_MODULE_NAME)

# Vérifs pour éviter les surprises
for fn in ("send_cmd", "read_line", "is_connected"):
    if not hasattr(arduino, fn):
        raise RuntimeError(
            f"Le module série '{SERIAL_MODULE_NAME}' ne contient pas '{fn}'. "
            f"Vérifie SERIAL_MODULE_NAME et le contenu de ton fichier."
        )


# =========================
# FLASK APP
# =========================
APP = Flask(__name__)


def _auth_ok(req) -> bool:
    return req.headers.get("X-ROVER-LOCAL-TOKEN", "") == LOCAL_TOKEN


def _normalize(cmd: str) -> str:
    c = (cmd or "").strip().upper()
    # alias
    if c == "BACKWARD":
        c = "BACK"
    return c


def _clamp_power(p) -> int:
    try:
        p = int(p)
    except Exception:
        return 50
    if p < 0:
        p = 0
    if p > 100:
        p = 100
    return p


def _to_arduino_line(cmd: str, power: int) -> str:
    """
    Protocole texte Arduino (d'après ton firmware SunFounder) :
      - stop
      - forward <power>
      - backward <power>
      - turn left <power>
      - turn right <power>
    """
    if cmd == "STOP":
        return "stop"
    if cmd == "FORWARD":
        return f"forward {power}"
    if cmd == "BACK":
        return f"backward {power}"
    if cmd == "LEFT":
        return f"turn left {power}"
    if cmd == "RIGHT":
        return f"turn right {power}"
    return ""


@APP.route("/health", methods=["GET"])
def health():
    return jsonify(
        ok=True,
        connected=arduino.is_connected(),
        ts=time.time(),
        serial_module=SERIAL_MODULE_NAME,
    )


@APP.route("/telemetry/last", methods=["GET"])
def telemetry_last():
    with _last_lock:
        return jsonify(ok=True, lines=list(_last_lines))


@APP.route("/motor", methods=["POST"])
def motor():
    if not _auth_ok(request):
        return jsonify(ok=False, error="unauthorized"), 401

    data = request.get_json(silent=True) or {}
    cmd = _normalize(data.get("cmd", ""))

    if not cmd:
        return jsonify(ok=False, error="missing_cmd"), 400

    # power optionnel
    power = _clamp_power(data.get("power", 50))

    # convertir en ligne série firmware
    line = _to_arduino_line(cmd, power)
    if not line:
        return jsonify(
            ok=False,
            error="bad_cmd",
            allowed=["FORWARD", "BACK", "LEFT", "RIGHT", "STOP"]
        ), 400

    sent = arduino.send_cmd(line)
    return jsonify(ok=True, sent=sent, cmd=cmd, power=power, line=line), (200 if sent else 503)


# STOP d'urgence (optionnel mais pratique)
@APP.route("/stop", methods=["POST"])
def emergency_stop():
    if not _auth_ok(request):
        return jsonify(ok=False, error="unauthorized"), 401

    line = "stop"
    sent = arduino.send_cmd(line)
    return jsonify(ok=True, sent=sent, cmd="STOP", line=line), (200 if sent else 503)


def _telemetry_collector():
    """Stocke les lignes lues depuis l'Arduino pour /telemetry/last."""
    while True:
        try:
            line = arduino.read_line()
            if line:
                with _last_lock:
                    _last_lines.appendleft(line)
        except Exception:
            # on ignore pour ne pas tuer le thread
            pass
        time.sleep(0.1)


def main():
    # Thread qui collecte la télémétrie pour l'API
    threading.Thread(target=_telemetry_collector, daemon=True).start()

    # Serveur HTTP local uniquement
    APP.run(host=HOST, port=PORT, threaded=True)


if __name__ == "__main__":
    main()

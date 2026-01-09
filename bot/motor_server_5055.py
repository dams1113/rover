from __future__ import annotations
from flask import Flask, request, jsonify
import time
import threading
from collections import deque

# 👉 Import de TON module série (celui que tu m'as montré)
# Mets ici le bon nom de fichier, ex: import arduino_link as arduino
import arduino as arduino  # <-- CHANGE "arduino" selon le nom réel de ton fichier

APP = Flask(__name__)

LOCAL_TOKEN = "local-change-moi-12345"  # doit matcher ROVER_LOCAL_TOKEN côté ai_rover
PORT = 5055

# buffer télémétrie (optionnel)
_last_lines = deque(maxlen=50)
_last_lock = threading.Lock()


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
    ⚠️ Adapte ici le protocole texte EXACT attendu par ton firmware.
    D'après ton code Arduino: "forward", "backward", "turn left", "turn right", "stop"
    et la notion power existe.
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
    return jsonify(ok=True, connected=arduino.is_connected(), ts=time.time())


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
        return jsonify(ok=False, error="bad_cmd", allowed=["FORWARD","BACK","LEFT","RIGHT","STOP"]), 400

    ok = arduino.send_cmd(line)
    return jsonify(ok=True, sent=ok, cmd=cmd, power=power, line=line), (200 if ok else 503)


def _telemetry_collector():
    """Optionnel : stocke les lignes lues depuis l'Arduino pour /telemetry/last."""
    while True:
        try:
            line = arduino.read_line()
            if line:
                with _last_lock:
                    _last_lines.appendleft(line)
        except Exception:
            pass
        time.sleep(0.1)


def main():
    # démarre le reader Discord si tu veux (facultatif)
    # arduino.start_reader()

    # thread qui collecte la télémétrie pour l'API
    threading.Thread(target=_telemetry_collector, daemon=True).start()

    APP.run(host="127.0.0.1", port=PORT, threaded=True)


if __name__ == "__main__":
    main()

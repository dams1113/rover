from flask import Flask, request, jsonify
import time
import threading

import serial

from ai_rover import config
from ai_rover import state

app = Flask(__name__)

# ===== CONFIG SERIE (même que ton bot Discord) =====
SERIAL_PORT = "/dev/arduino"
SERIAL_BAUD = 9600

_ser = None
_lock = threading.Lock()


def check_auth(req) -> bool:
    return req.headers.get("X-ROVER-TOKEN", "") == config.ROVER_TOKEN


def _connect():
    global _ser
    if _ser and _ser.is_open:
        return True
    try:
        _ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        try:
            _ser.dtr = False
            _ser.rts = False
        except Exception:
            pass
        time.sleep(0.2)
        try:
            _ser.reset_input_buffer()
        except Exception:
            pass
        print(f"[AI_ROVER] ✅ Serial connected: {SERIAL_PORT} @ {SERIAL_BAUD}")
        return True
    except Exception as e:
        print(f"[AI_ROVER] ❌ Serial connect failed: {e}")
        _ser = None
        return False


def _send(code: str):
    """
    Envoie un code Arduino (F,B,L,R,S...) sans faire planter le serveur.
    Retourne (sent: bool, note: str)
    """
    global _ser
    with _lock:
        if not _connect():
            return False, "serial_not_connected"
        try:
            _ser.write((code + "\n").encode())
            return True, "ok"
        except Exception as e:
            print(f"[AI_ROVER] ⚠️ Serial write failed: {e}")
            try:
                _ser.close()
            except Exception:
                pass
            _ser = None
            return False, "serial_write_failed"


# Mapping commandes API -> codes Arduino (identiques à ton bot)
CMD_TO_CODE = {
    "FORWARD": "F",
    "BACK": "B",
    "LEFT": "L",
    "RIGHT": "R",
    "STOP": "S",
}


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify(ok=True, armed=state.ARMED, last_cmd=state.LAST_CMD, last_ts=state.LAST_TS)


@app.route("/arm", methods=["POST"])
def arm():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401
    state.ARMED = True
    print("[AI_ROVER] ARMED = True")
    return jsonify(ok=True, armed=True)


@app.route("/disarm", methods=["POST"])
def disarm():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401
    state.ARMED = False
    sent, note = _send("S")  # STOP
    state.LAST_CMD = "STOP"
    state.LAST_TS = time.time()
    print("[AI_ROVER] ARMED = False (DISARM) + STOP")
    return jsonify(ok=True, armed=False, cmd="STOP", sent=sent, note=note)


@app.route("/cmd", methods=["POST"])
def cmd():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401

    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").upper().strip()

    if not cmd:
        return jsonify(ok=False, error="missing_cmd"), 400

    # STOP toujours autorisé
    if cmd == "STOP":
        sent, note = _send("S")
        state.LAST_CMD = "STOP"
        state.LAST_TS = time.time()
        return jsonify(ok=True, armed=state.ARMED, cmd="STOP", sent=sent, note=note)

    # Refuse si pas armé
    if not state.ARMED:
        _send("S")
        state.LAST_CMD = "STOP"
        state.LAST_TS = time.time()
        return jsonify(ok=False, error="NOT_ARMED", armed=False, cmd="STOP"), 403

    if cmd not in CMD_TO_CODE:
        return jsonify(ok=False, error="BAD_CMD"), 400

    code = CMD_TO_CODE[cmd]
    sent, note = _send(code)
    state.LAST_CMD = cmd if sent else "STOP"
    state.LAST_TS = time.time()
    return jsonify(ok=True, armed=True, cmd=cmd, sent=sent, note=note)


def start_server():
    print(f"[AI_ROVER] Starting command server on {config.SERVER_HOST}:{config.SERVER_PORT}")
    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, threaded=True)

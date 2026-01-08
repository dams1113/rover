from flask import Flask, request, jsonify
import time
import os
import requests

from ai_rover import config
from ai_rover import state

app = Flask(__name__)

BOT_API_URL = os.getenv("ROVER_BOT_API_URL", "http://127.0.0.1:5055/motor")
LOCAL_TOKEN = os.getenv("ROVER_LOCAL_TOKEN", "local-change-moi-12345")


def check_auth(req) -> bool:
    return req.headers.get("X-ROVER-TOKEN", "") == config.ROVER_TOKEN


def _send_to_bot(cmd: str):
    """Envoie la commande au bot local (qui possède le port série)."""
    try:
        r = requests.post(
            BOT_API_URL,
            json={"cmd": cmd},
            headers={"X-ROVER-LOCAL-TOKEN": LOCAL_TOKEN},
            timeout=1.0,
        )
        if r.status_code == 200:
            return True, "ok"
        return False, f"bot_api_{r.status_code}"
    except Exception as e:
        return False, f"bot_api_down:{e.__class__.__name__}"


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify(ok=True, armed=state.ARMED, last_cmd=state.LAST_CMD, last_ts=state.LAST_TS)


@app.route("/arm", methods=["POST"])
def arm():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401
    state.ARMED = True
    return jsonify(ok=True, armed=True)


@app.route("/disarm", methods=["POST"])
def disarm():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401

    state.ARMED = False
    sent, note = _send_to_bot("STOP")
    state.LAST_CMD = "STOP"
    state.LAST_TS = time.time()
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
        sent, note = _send_to_bot("STOP")
        state.LAST_CMD = "STOP"
        state.LAST_TS = time.time()
        return jsonify(ok=True, armed=state.ARMED, cmd="STOP", sent=sent, note=note)

    # refuse mouvements si pas armé
    if not state.ARMED:
        _send_to_bot("STOP")
        state.LAST_CMD = "STOP"
        state.LAST_TS = time.time()
        return jsonify(ok=False, error="NOT_ARMED", armed=False), 403

    if cmd not in ("FORWARD", "LEFT", "RIGHT", "BACK"):
        return jsonify(ok=False, error="BAD_CMD"), 400

    sent, note = _send_to_bot(cmd)
    state.LAST_CMD = cmd if sent else "STOP"
    state.LAST_TS = time.time()
    return jsonify(ok=True, armed=True, cmd=cmd, sent=sent, note=note)


def start_server():
    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, threaded=True)

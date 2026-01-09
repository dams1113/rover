from flask import Flask, request, jsonify
import time
import os
import threading
import requests

from ai_rover import config
from ai_rover import state

app = Flask(__name__)

BOT_API_URL = os.getenv("ROVER_BOT_API_URL", "http://127.0.0.1:5055/motor")
LOCAL_TOKEN = os.getenv("ROVER_LOCAL_TOKEN", "local-change-moi-12345")


# -------------------------
# Helpers
# -------------------------
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


def _normalize_cmd(cmd: str) -> str:
    c = (cmd or "").upper().strip()
    # alias
    if c == "BACKWARD":
        return "BACK"
    return c


def _record_last(cmd: str):
    state.LAST_CMD = cmd
    state.LAST_TS = time.time()


def _timed_stop(delay_ms: int):
    """Stoppe après delay_ms (thread séparé)."""
    try:
        time.sleep(delay_ms / 1000.0)
        _send_to_bot("STOP")
        _record_last("STOP")
    except Exception:
        pass


# -------------------------
# Mode state (simple)
# -------------------------
if not hasattr(state, "MODE"):
    state.MODE = None
if not hasattr(state, "MODE_SINCE"):
    state.MODE_SINCE = None
if not hasattr(state, "MODE_TARGET"):
    state.MODE_TARGET = {}
if not hasattr(state, "MODE_PARAMS"):
    state.MODE_PARAMS = {}
if not hasattr(state, "LAST_ERROR"):
    state.LAST_ERROR = None


def _set_mode(mode: str, target: dict | None = None, params: dict | None = None):
    state.MODE = mode
    state.MODE_SINCE = time.time()
    state.MODE_TARGET = target or {}
    state.MODE_PARAMS = params or {}
    state.LAST_ERROR = None


def _clear_mode():
    state.MODE = None
    state.MODE_SINCE = None
    state.MODE_TARGET = {}
    state.MODE_PARAMS = {}


# -------------------------
# Routes
# -------------------------
@app.route("/ping", methods=["GET"])
def ping():
    return jsonify(ok=True, armed=state.ARMED, last_cmd=state.LAST_CMD, last_ts=state.LAST_TS)


@app.route("/state", methods=["GET"])
def get_state():
    return jsonify(
        ok=True,
        armed=state.ARMED,
        last_cmd=state.LAST_CMD,
        last_ts=state.LAST_TS,
        mode=state.MODE,
        mode_since=state.MODE_SINCE,
        mode_target=state.MODE_TARGET,
        mode_params=state.MODE_PARAMS,
        last_error=state.LAST_ERROR,
        bot_api_url=BOT_API_URL,
    )


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
    _clear_mode()

    sent, note = _send_to_bot("STOP")
    _record_last("STOP")
    return jsonify(ok=True, armed=False, cmd="STOP", sent=sent, note=note)


@app.route("/cmd", methods=["POST"])
def cmd():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401

    data = request.get_json(silent=True) or {}
    raw_cmd = data.get("cmd")
    ms = data.get("ms", None)

    cmd = _normalize_cmd(raw_cmd)

    if not cmd:
        return jsonify(ok=False, error="missing_cmd"), 400

    # STOP toujours autorisé
    if cmd == "STOP":
        sent, note = _send_to_bot("STOP")
        _record_last("STOP")
        return jsonify(ok=True, armed=state.ARMED, cmd="STOP", sent=sent, note=note)

    # refuse mouvements si pas armé
    if not state.ARMED:
        _send_to_bot("STOP")
        _record_last("STOP")
        return jsonify(ok=False, error="NOT_ARMED", armed=False), 403

    # cmd autorisées
    if cmd not in ("FORWARD", "LEFT", "RIGHT", "BACK"):
        return jsonify(ok=False, error="BAD_CMD"), 400

    sent, note = _send_to_bot(cmd)
    if sent:
        _record_last(cmd)
    else:
        _send_to_bot("STOP")
        _record_last("STOP")

    # commande temporisée (ms)
    if isinstance(ms, int) and 0 < ms <= 60000 and sent:
        threading.Thread(target=_timed_stop, args=(ms,), daemon=True).start()

    return jsonify(ok=True, armed=True, cmd=cmd, sent=sent, note=note, ms=ms if isinstance(ms, int) else None)


# -------------------------
# Modes API (stockage + stop safe)
# -------------------------
@app.route("/mode/start", methods=["POST"])
def mode_start():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401

    body = request.get_json(silent=True) or {}
    mode = (body.get("mode") or "").upper().strip()
    target = body.get("target") or {}
    params = body.get("params") or {}

    if mode not in ("FOLLOW_X", "GOTO_GPS"):
        return jsonify(ok=False, error="unsupported_mode", allowed=["FOLLOW_X", "GOTO_GPS"]), 400

    if not state.ARMED:
        return jsonify(ok=False, error="NOT_ARMED", armed=False), 403

    _set_mode(mode, target=target, params=params)
    return jsonify(ok=True, message="mode_started", mode=state.MODE, state_target=state.MODE_TARGET, state_params=state.MODE_PARAMS)


@app.route("/mode/stop", methods=["POST"])
def mode_stop():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401

    _clear_mode()
    sent, note = _send_to_bot("STOP")
    _record_last("STOP")
    return jsonify(ok=True, message="mode_stopped", sent=sent, note=note)


@app.route("/goto", methods=["POST"])
def goto():
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401

    if not state.ARMED:
        return jsonify(ok=False, error="NOT_ARMED", armed=False), 403

    body = request.get_json(silent=True) or {}
    lat = body.get("lat")
    lon = body.get("lon")
    speed = body.get("speed", 50)
    radius_m = body.get("radius_m", 3)

    if lat is None or lon is None:
        return jsonify(ok=False, error="missing_lat_lon"), 400

    try:
        lat = float(lat)
        lon = float(lon)
        speed = int(speed)
        radius_m = int(radius_m)
    except Exception:
        return jsonify(ok=False, error="bad_params"), 400

    _set_mode("GOTO_GPS", target={"lat": lat, "lon": lon}, params={"speed": speed, "radius_m": radius_m})
    return jsonify(ok=True, message="goto_set", mode=state.MODE, target=state.MODE_TARGET, params=state.MODE_PARAMS)


def start_server():
    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, threaded=True)

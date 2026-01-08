from flask import Flask, request, jsonify
import time

from ai_rover import config
from ai_rover import state

# Module moteur existant (adaptable si ton module a un autre nom)
from modules import arduino_link

app = Flask(__name__)


# =========================
# Sécurité
# =========================

def check_auth(req) -> bool:
    return req.headers.get("X-ROVER-TOKEN", "") == config.ROVER_TOKEN


# =========================
# Wrappers moteurs (anti-crash)
# =========================

def _safe_call(fn_name: str, fn):
    """
    Exécute une action moteur sans jamais faire planter Flask.
    Retourne (ok: bool, note: str)
    """
    try:
        fn()
        return True, "ok"
    except Exception as e:
        # On log mais on ne crash jamais
        print(f"[AI_ROVER] {fn_name} ignored (arduino not ready): {e}")
        return False, "arduino_not_ready"


def motors_stop():
    return _safe_call("STOP", lambda: arduino_link.stop())


def motors_forward():
    return _safe_call("FORWARD", lambda: arduino_link.forward(config.SPEED_FORWARD))


def motors_left():
    return _safe_call("LEFT", lambda: arduino_link.left(config.SPEED_TURN))


def motors_right():
    return _safe_call("RIGHT", lambda: arduino_link.right(config.SPEED_TURN))


# =========================
# Routes HTTP
# =========================

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify(
        ok=True,
        armed=state.ARMED,
        last_cmd=state.LAST_CMD,
        last_ts=state.LAST_TS
    )


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
    ok, note = motors_stop()
    state.LAST_CMD = "STOP"
    state.LAST_TS = time.time()

    print("[AI_ROVER] ARMED = False (DISARM) + STOP")
    return jsonify(ok=True, armed=False, cmd="STOP", note=note)


@app.route("/cmd", methods=["POST"])
def cmd():
    """
    Body JSON:
      { "cmd": "STOP|FORWARD|LEFT|RIGHT" }

    STOP est toujours autorisé même si DISARM.
    Les autres commandes sont refusées si DISARM.
    """
    if not check_auth(request):
        return jsonify(ok=False, error="unauthorized"), 401

    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").upper().strip()

    if not cmd:
        return jsonify(ok=False, error="missing_cmd"), 400

    # STOP toujours autorisé
    if cmd == "STOP":
        ok, note = motors_stop()
        state.LAST_CMD = "STOP"
        state.LAST_TS = time.time()
        return jsonify(ok=True, armed=state.ARMED, cmd="STOP", note=note)

    # Refuse mouvement si pas armé
    if not state.ARMED:
        # On stop quand même par sécurité
        motors_stop()
        state.LAST_CMD = "STOP"
        state.LAST_TS = time.time()
        return jsonify(ok=False, error="NOT_ARMED", armed=False, cmd="STOP"), 403

    # Exécuter commande
    if cmd == "FORWARD":
        ok, note = motors_forward()
    elif cmd == "LEFT":
        ok, note = motors_left()
    elif cmd == "RIGHT":
        ok, note = motors_right()
    else:
        return jsonify(ok=False, error="BAD_CMD"), 400

    # Même si l'arduino n'est pas prêt, on garde l'état cohérent
    state.LAST_CMD = cmd if ok else "STOP"
    state.LAST_TS = time.time()

    return jsonify(ok=True, armed=True, cmd=cmd, note=note)


# =========================
# Lancement
# =========================

def start_server():
    print(f"[AI_ROVER] Starting command server on {config.SERVER_HOST}:{config.SERVER_PORT}")
    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, threaded=True)

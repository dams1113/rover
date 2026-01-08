from flask import Flask, request, jsonify
import time

from ai_rover import config
from ai_rover import state

# ⚠️ adapte si ton module moteur a un autre nom
from modules import arduino_link

app = Flask(__name__)

def check_auth(req):
    return req.headers.get("X-ROVER-TOKEN") == config.ROVER_TOKEN

# ===== moteurs =====

def motors_stop():
    arduino_link.stop()

def motors_forward():
    arduino_link.forward(config.SPEED_FORWARD)

def motors_left():
    arduino_link.left(config.SPEED_TURN)

def motors_right():
    arduino_link.right(config.SPEED_TURN)

# ===== routes =====

@app.route("/ping", methods=["GET"])
def ping():
    return jsonify(ok=True, armed=state.ARMED, last_cmd=state.LAST_CMD)

@app.route("/arm", methods=["POST"])
def arm():
    if not check_auth(request):
        return jsonify(ok=False), 401
    state.ARMED = True
    return jsonify(ok=True, armed=True)

@app.route("/disarm", methods=["POST"])
def disarm():
    if not check_auth(request):
        return jsonify(ok=False), 401
    state.ARMED = False
    motors_stop()
    state.LAST_CMD = "STOP"
    return jsonify(ok=True, armed=False)

@app.route("/cmd", methods=["POST"])
def cmd():
    if not check_auth(request):
        return jsonify(ok=False), 401

    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").upper()

    if cmd == "STOP":
        motors_stop()
        state.LAST_CMD = "STOP"
        state.LAST_TS = time.time()
        return jsonify(ok=True, cmd="STOP")

    if not state.ARMED:
        motors_stop()
        return jsonify(ok=False, error="NOT_ARMED"), 403

    if cmd == "FORWARD":
        motors_forward()
    elif cmd == "LEFT":
        motors_left()
    elif cmd == "RIGHT":
        motors_right()
    else:
        return jsonify(ok=False, error="BAD_CMD"), 400

    state.LAST_CMD = cmd
    state.LAST_TS = time.time()
    return jsonify(ok=True, cmd=cmd)

def start_server():
    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, threaded=True)

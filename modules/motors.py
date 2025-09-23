# modules/motors.py
import time

try:
    from robot_hat import Motor
    _HAVE_ROBOT_HAT = True
except Exception as e:
    _HAVE_ROBOT_HAT = False
    print("[MOTORS] robot_hat introuvable ou erreur d'import:", e)

if _HAVE_ROBOT_HAT:
    _motor_left = Motor("M1")
    _motor_right = Motor("M2")
else:
    _motor_left = _motor_right = None

def _clamp_speed(v: int) -> int:
    return max(-100, min(100, int(v)))

def set_speeds(left: int, right: int):
    """
    Vitesse en pourcentage [-100..100]
    """
    l = _clamp_speed(left)
    r = _clamp_speed(right)
    if _HAVE_ROBOT_HAT:
        _motor_left.speed(l)
        _motor_right.speed(r)
    else:
        print(f"[MOTORS] set_speeds(left={l}, right={r}) (FAKE)")

def stop():
    if _HAVE_ROBOT_HAT:
        _motor_left.stop()
        _motor_right.stop()
    else:
        print("[MOTORS] stop() (FAKE)")

def forward(speed=50, duration=None):
    set_speeds(speed, speed)
    if duration:
        time.sleep(duration)
        stop()

def backward(speed=50, duration=None):
    set_speeds(-speed, -speed)
    if duration:
        time.sleep(duration)
        stop()

def turn_left(speed=50, duration=None):
    set_speeds(-speed, speed)
    if duration:
        time.sleep(duration)
        stop()

def turn_right(speed=50, duration=None):
    set_speeds(speed, -speed)
    if duration:
        time.sleep(duration)
        stop()

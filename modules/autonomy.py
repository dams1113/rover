# modules/autonomy.py
import threading
import time
from modules import motors, gps_reader

try:
    from robot_hat import Ultrasonic
    _HAVE_ULTRASONIC = True
except Exception as e:
    _HAVE_ULTRASONIC = False
    print("[AUTO] Ultrasonic indisponible:", e)

class AutonomousController:
    def __init__(self, speed=45, obstacle_cm=20, tick_s=0.4):
        self.speed = int(speed)
        self.obstacle_cm = int(obstacle_cm)
        self.tick_s = float(tick_s)
        self._run = False
        self._thread = None
        self._ultra = Ultrasonic() if _HAVE_ULTRASONIC else None

    def is_running(self) -> bool:
        return self._run and self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running():
            return
        self._run = True
        self._thread = threading.Thread(target=self._loop, name="autonomy", daemon=True)
        self._thread.start()
        print("[AUTO] démarré")

    def stop(self):
        self._run = False
        print("[AUTO] arrêt demandé")

    def _read_distance(self):
        if not self._ultra:
            return None
        try:
            return self._ultra.read()  # en cm
        except Exception as e:
            print("[AUTO] Erreur lecture ultrason:", e)
            return None

    def _loop(self):
        try:
            while self._run:
                dist = self._read_distance()
                avoid = dist is not None and dist > 0 and dist < self.obstacle_cm

                if avoid:
                    # Obstacle : stop + évitement gauche court
                    motors.stop()
                    motors.turn_left(speed=self.speed, duration=0.6)
                else:
                    # Avance par petits pas pour rester réactif
                    motors.forward(speed=self.speed, duration=self.tick_s)

                # GPS debug (non bloquant)
                try:
                    pos = gps_reader.get_gps_data()
                    # pos peut être None / dict selon ton module
                    print(f"[AUTO] GPS: {pos}")
                except Exception as e:
                    print("[AUTO] Erreur GPS:", e)

                # petite pause pour respiration de la boucle (déjà gérée via duration)
                time.sleep(0.05)

        finally:
            motors.stop()
            print("[AUTO] boucle terminée")

# Singleton simple utilisable depuis le bot
_controller = AutonomousController()

def auto_start():
    _controller.start()

def auto_stop():
    _controller.stop()

def auto_status() -> str:
    return "running" if _controller.is_running() else "stopped"

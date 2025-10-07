import serial
import time
import threading

# --- Configuration du port série ---
# Vérifie ton port avec : ls /dev/tty*
# Exemples : /dev/ttyUSB0 ou /dev/ttyACM0
PORT = "/dev/ttyUSB0"
BAUDRATE = 9600

ser = None
lock = threading.Lock()

def connect_arduino():
    """Initialise la connexion série avec l'Arduino."""
    global ser
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        time.sleep(2)
        print(f"[Arduino] Connecté sur {PORT} à {BAUDRATE} baud.")
        return True
    except serial.SerialException as e:
        print(f"[Arduino] Erreur de connexion : {e}")
        return False

def send_cmd(cmd: str):
    """Envoie une commande texte à l'Arduino."""
    global ser
    if not ser:
        if not connect_arduino():
            print("[Arduino] Non connecté — commande ignorée.")
            return
    with lock:
        ser.write((cmd + "\n").encode())
        print(f"[Arduino] → {cmd}")

def read_line():
    """Lit une ligne envoyée par l’Arduino (si disponible)."""
    global ser
    if ser and ser.in_waiting:
        line = ser.readline().decode(errors='ignore').strip()
        if line:
            print(f"[Arduino] ← {line}")
        return line
    return None

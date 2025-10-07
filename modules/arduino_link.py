import serial
import time
import threading

PORT = "/dev/ttyUSB0"   # vérifie avec ls /dev/tty*
BAUDRATE = 9600
ser = None
lock = threading.Lock()
discord_channel = None  # sera défini par discord_bot

def connect_arduino():
    """Initialise la connexion série."""
    global ser
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        time.sleep(2)
        print(f"[Arduino] ✅ Connecté sur {PORT}")
        return True
    except serial.SerialException as e:
        print(f"[Arduino] ❌ Erreur de connexion : {e}")
        return False

def send_cmd(cmd: str):
    """Envoie une commande texte à l'Arduino."""
    global ser
    if not ser:
        if not connect_arduino():
            return
    with lock:
        ser.write((cmd + "\n").encode())
        print(f"[Arduino] → {cmd}")

def read_line():
    """Lit une ligne brute depuis Arduino."""
    global ser
    if ser and ser.in_waiting:
        try:
            line = ser.readline().decode(errors='ignore').strip()
            if line:
                print(f"[Arduino] ← {line}")
            return line
        except Exception:
            pass
    return None

def _reader_loop():
    """Boucle continue qui lit les messages Arduino et les envoie sur Discord."""
    global discord_channel
    while True:
        line = read_line()
        if line and discord_channel:
            try:
                # Exemple: "BAT:87%;DIST:32.5cm;IR_L:1;IR_R:0"
                discord_message = (
                    "📡 **Télémetrie Arduino**\n"
                    f"```\n{line}\n```"
                )
                # envoi asynchrone
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    discord_channel.send(discord_message),
                    discord_channel._state.loop
                )
            except Exception as e:
                print(f"[Arduino] ⚠️ Erreur Discord : {e}")
        time.sleep(1)

# Lancement automatique du thread de lecture
threading.Thread(target=_reader_loop, daemon=True).start()

import serial
import serial.tools.list_ports
import time
import threading
import asyncio

# --- CONFIGURATION ---
BAUDRATE = 9600
ser = None
lock = threading.Lock()
discord_channel = None  # sera défini par discord_bot
running = True

# --------------------------------------------------------------------
# 🔍 Détection automatique du port Arduino
# --------------------------------------------------------------------
def find_arduino_port():
    """Détecte automatiquement le port série de l’Arduino."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = port.description.lower()
        if "arduino" in desc or "ch340" in desc or "ftdi" in desc:
            print(f"[Arduino] 🔍 Détecté sur {port.device} ({desc})")
            return port.device
    print("[Arduino] ⚠️ Aucun port compatible trouvé.")
    return None


# --------------------------------------------------------------------
# 🔌 Connexion
# --------------------------------------------------------------------
def connect_arduino():
    """Initialise la connexion série avec détection automatique."""
    global ser

    port = find_arduino_port()
    if not port:
        return False

    try:
        ser = serial.Serial(port, BAUDRATE, timeout=1)
        ser.dtr = False   # empêche le reset automatique
        ser.rts = False
        time.sleep(1)
        ser.reset_input_buffer()
        print(f"[Arduino] ✅ Connecté sur {port}")
        return True
    except serial.SerialException as e:
        print(f"[Arduino] ❌ Erreur de connexion : {e}")
        ser = None
        return False


# --------------------------------------------------------------------
# 📨 Envoi
# --------------------------------------------------------------------
def send_cmd(cmd: str):
    """Envoie une commande texte à l'Arduino."""
    global ser
    if not ser or not ser.is_open:
        print("[Arduino] 🔄 Reconnexion en cours...")
        if not connect_arduino():
            print("[Arduino] ❌ Impossible d’envoyer la commande, Arduino non connecté.")
            return
    with lock:
        try:
            ser.write((cmd + "\n").encode())
            print(f"[Arduino] → {cmd}")
        except Exception as e:
            print(f"[Arduino] ⚠️ Erreur d’envoi : {e}")
            try:
                ser.close()
            except Exception:
                pass
            ser = None


# --------------------------------------------------------------------
# 📥 Lecture
# --------------------------------------------------------------------
def read_line():
    """Lit une ligne brute depuis l’Arduino."""
    global ser
    if ser and ser.is_open and ser.in_waiting:
        try:
            line = ser.readline().decode(errors='ignore').strip()
            if line:
                print(f"[Arduino] ← {line}")
            return line
        except Exception as e:
            print(f"[Arduino] ⚠️ Erreur lecture : {e}")
            try:
                ser.close()
            except Exception:
                pass
            ser = None
    return None


# --------------------------------------------------------------------
# 🔁 Boucle de lecture (thread)
# --------------------------------------------------------------------
def _reader_loop():
    """Boucle continue : lit les messages Arduino et les envoie sur Discord."""
    global discord_channel, running
    print("[Arduino] 🧠 Démarrage du thread de lecture série...")

    while running:
        line = read_line()

        if line and discord_channel:
            try:
                discord_message = f"📡 **Télémétrie Arduino**\n```\n{line}\n```"
                asyncio.run_coroutine_threadsafe(
                    discord_channel.send(discord_message),
                    discord_channel._state.loop
                )
            except Exception as e:
                print(f"[Arduino] ⚠️ Erreur envoi Discord : {e}")

        # si plus de port, on tente de se reconnecter
        if not ser or not ser.is_open:
            print("[Arduino] ⚠️ Déconnexion détectée — tentative de reconnexion...")
            connect_arduino()

        time.sleep(1.0)


# --------------------------------------------------------------------
# 🚀 Lancement automatique
# --------------------------------------------------------------------
def start_reader():
    """Démarre le thread de lecture série (si pas déjà lancé)."""
    global running
    running = True
    threading.Thread(target=_reader_loop, daemon=True).start()
    print("[Arduino] 🧩 Thread de lecture série lancé.")

# Démarrage immédiat du thread
start_reader()

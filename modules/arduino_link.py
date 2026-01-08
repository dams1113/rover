import serial
import serial.tools.list_ports
import time
import threading
import asyncio

# --- CONFIGURATION ---
BAUDRATE = 9600
PREFERRED_PORTS = ["/dev/ttyUSB0", "/dev/ttyACM0"]  # on force en priorité

ser = None
lock = threading.Lock()

discord_channel = None  # sera défini par discord_bot
running = False
_reader_thread = None


# --------------------------------------------------------------------
# 🔍 Détection du port Arduino (avec priorité)
# --------------------------------------------------------------------
def find_arduino_port():
    """Détecte automatiquement le port série de l’Arduino, avec priorité."""
    # 1) ports préférés d'abord
    ports = {p.device: (p.description or "").lower() for p in serial.tools.list_ports.comports()}

    for pref in PREFERRED_PORTS:
        if pref in ports:
            desc = ports[pref]
            print(f"[Arduino] 🔍 Port préféré trouvé: {pref} ({desc})")
            return pref

    # 2) sinon scan classique
    for dev, desc in ports.items():
        if "arduino" in desc or "ch340" in desc or "ftdi" in desc:
            print(f"[Arduino] 🔍 Détecté sur {dev} ({desc})")
            return dev

    print("[Arduino] ⚠️ Aucun port compatible trouvé.")
    return None


# --------------------------------------------------------------------
# 🔌 Connexion / Déconnexion
# --------------------------------------------------------------------
def is_connected():
    return ser is not None and ser.is_open


def connect_arduino():
    """Initialise la connexion série avec détection automatique."""
    global ser

    if is_connected():
        return True

    port = find_arduino_port()
    if not port:
        return False

    try:
        ser = serial.Serial(port, BAUDRATE, timeout=1)
        # évite certains resets auto
        try:
            ser.dtr = False
            ser.rts = False
        except Exception:
            pass

        time.sleep(1)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        print(f"[Arduino] ✅ Connecté sur {port} @ {BAUDRATE}")
        return True

    except Exception as e:
        print(f"[Arduino] ❌ Erreur de connexion : {e}")
        ser = None
        return False


def disconnect_arduino():
    """Ferme proprement la connexion série."""
    global ser
    with lock:
        try:
            if ser and ser.is_open:
                ser.close()
        except Exception:
            pass
        ser = None


# --------------------------------------------------------------------
# 📨 Envoi
# --------------------------------------------------------------------
def send_cmd(cmd: str) -> bool:
    """Envoie une commande texte à l'Arduino. Retourne True si envoyé."""
    global ser

    if not is_connected():
        # tentative unique de connexion (pas de boucle agressive)
        if not connect_arduino():
            print("[Arduino] ❌ Arduino non connecté, commande ignorée:", cmd)
            return False

    with lock:
        try:
            ser.write((cmd + "\n").encode())
            # print(f"[Arduino] → {cmd}")
            return True
        except Exception as e:
            print(f"[Arduino] ⚠️ Erreur d’envoi : {e}")
            disconnect_arduino()
            return False


# --------------------------------------------------------------------
# 📥 Lecture
# --------------------------------------------------------------------
def read_line():
    """Lit une ligne brute depuis l’Arduino."""
    global ser
    if is_connected():
        try:
            if ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()
                if line:
                    # print(f"[Arduino] ← {line}")
                    return line
        except Exception as e:
            print(f"[Arduino] ⚠️ Erreur lecture : {e}")
            disconnect_arduino()
    return None


# --------------------------------------------------------------------
# 🔁 Boucle de lecture (thread)
# --------------------------------------------------------------------
def _reader_loop():
    """Boucle continue : lit les messages Arduino et les envoie sur Discord."""
    global discord_channel, running

    print("[Arduino] 🧠 Thread de lecture série démarré.")
    while running:
        # si pas connecté, tentative douce (toutes les 2s)
        if not is_connected():
            connect_arduino()
            time.sleep(2.0)
            continue

        line = read_line()

        if line and discord_channel:
            try:
                msg = f"📡 **Télémétrie Arduino**\n```\n{line}\n```"
                asyncio.run_coroutine_threadsafe(
                    discord_channel.send(msg),
                    discord_channel._state.loop
                )
            except Exception as e:
                print(f"[Arduino] ⚠️ Erreur envoi Discord : {e}")

        time.sleep(0.2)

    print("[Arduino] 🛑 Thread de lecture arrêté.")


# --------------------------------------------------------------------
# 🚀 Contrôle du thread (IMPORTANT : plus d'auto-start à l'import)
# --------------------------------------------------------------------
def start_reader():
    """Démarre le thread de lecture série (si pas déjà lancé)."""
    global running, _reader_thread
    if _reader_thread and _reader_thread.is_alive():
        return

    running = True
    _reader_thread = threading.Thread(target=_reader_loop, daemon=True)
    _reader_thread.start()


def stop_reader():
    """Stoppe le thread de lecture."""
    global running
    running = False

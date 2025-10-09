import os
import re
import discord
import subprocess
import datetime
import psutil
import time
import asyncio
import serial
import serial.tools.list_ports
import logging

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()
CHANNEL_NAME = "communication-rover"  # salon Discord
BAUDRATE_ARDUINO = 9600
READ_INTERVAL = 10.0                  # lecture série (secondes)
SEND_INTERVAL = 3600                  # délai min entre télémétries (1h)
SEUIL_DIST = 1.0                      # seuil de tolérance (cm)
SEUIL_BAT = 1.0                       # seuil de tolérance (%)

# --- LOGGING ---
LOG_PATH = "/home/rover/rover/rover_serial.log"
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- Discord ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- VARIABLES GLOBALES ---
ser = None
PORT_ARDUINO = None
last_line = ""
last_sent_time = 0

PYTHON_BIN = "/home/rover/rover/.venv/bin/python"

# -------------------------------------------------------------
# 🔍 Détection automatique du port Arduino
# -------------------------------------------------------------
def find_arduino_port():
    """Détecte automatiquement le port série de l’Arduino."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = port.description.lower()
        if "arduino" in desc or "ch340" in desc or "ftdi" in desc:
            print(f"[SERIAL] 🔍 Arduino détecté sur {port.device} ({desc})")
            return port.device
    print("[SERIAL] ⚠️ Aucun périphérique Arduino détecté.")
    return None


# -------------------------------------------------------------
# 🔌 Connexion série
# -------------------------------------------------------------
def connect_arduino():
    """Initialise la connexion série à l’Arduino."""
    global ser, PORT_ARDUINO
    PORT_ARDUINO = find_arduino_port()
    if not PORT_ARDUINO:
        return False
    try:
        ser = serial.Serial(PORT_ARDUINO, BAUDRATE_ARDUINO, timeout=1)
        ser.dtr = False
        ser.rts = False
        time.sleep(1)
        ser.reset_input_buffer()
        print(f"[SERIAL] ✅ Connecté à {PORT_ARDUINO}")
        logging.info(f"Connexion initiale à {PORT_ARDUINO}")
        return True
    except Exception as e:
        print(f"[SERIAL] ❌ Erreur de connexion Arduino : {e}")
        logging.error(f"Erreur connexion initiale : {e}")
        ser = None
        return False


# -------------------------------------------------------------
# ⚙️ Lecture série (boucle asynchrone)
# -------------------------------------------------------------
async def serial_reader():
    """Lit la série Arduino et gère automatiquement les déconnexions."""
    global ser, last_line, last_sent_time, PORT_ARDUINO

    await client.wait_until_ready()
    channel = discord.utils.get(client.get_all_channels(), name=CHANNEL_NAME)

    while not client.is_closed():
        try:
            # connexion initiale
            if ser is None or not ser.is_open:
                if not connect_arduino():
                    await asyncio.sleep(5)
                    continue
                if channel:
                    await channel.send(f"♻️ **Arduino connecté sur {PORT_ARDUINO}** ✅")

            # lecture série
            if ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    await asyncio.sleep(READ_INTERVAL)
                    continue

                print(f"[SERIAL] {line}")
                logging.info(f"Lecture série : {line}")

                # Commandes directes Arduino
                if line.startswith("CMD:") and channel:
                    await channel.send(f"🖥️ **Arduino →** `{line}`")

                # ----------- TÉLÉMÉTRIE -----------
                if "BAT:" in line:
                    now = time.time()

                    bat_match = re.search(r"BAT[:=]\s*([\d\.]+)", line)
                    dist_match = re.search(r"DIST[:=]\s*([\d\.]+)", line)
                    bat_now = float(bat_match.group(1)) if bat_match else None
                    dist_now = float(dist_match.group(1)) if dist_match else None

                    bat_prev = None
                    dist_prev = None
                    if last_line:
                        bat_prev_match = re.search(r"BAT[:=]\s*([\d\.]+)", last_line)
                        dist_prev_match = re.search(r"DIST[:=]\s*([\d\.]+)", last_line)
                        bat_prev = float(bat_prev_match.group(1)) if bat_prev_match else None
                        dist_prev = float(dist_prev_match.group(1)) if dist_prev_match else None

                    dist_change = (dist_prev is None or dist_now is None or abs(dist_now - dist_prev) > SEUIL_DIST)
                    bat_change = (bat_prev is None or bat_now is None or abs(bat_now - bat_prev) > SEUIL_BAT)

                    if (dist_change or bat_change) or (now - last_sent_time) > SEND_INTERVAL:
                        last_line = line
                        last_sent_time = now

                        bat = re.search(r"BAT[:=]\s*([\d\.]+%?)", line)
                        dist = re.search(r"DIST[:=]\s*([\d\.]+cm?)", line)
                        ir_l = re.search(r"IR_L[:=]\s*(\d)", line)
                        ir_r = re.search(r"IR_R[:=]\s*(\d)", line)

                        msg = "📡 **Télémétrie Arduino**\n"
                        if bat:  msg += f"🔋 Batterie : `{bat.group(1)}`\n"
                        if dist: msg += f"📏 Distance : `{dist.group(1)}`\n"
                        if ir_l and ir_r:
                            msg += f"👁️ IR Gauche : `{ir_l.group(1)}` | Droite : `{ir_r.group(1)}`"

                        if channel:
                            await channel.send(msg)

        except (serial.SerialException, OSError) as e:
            print(f"[SERIAL] ⚠️ Déconnexion détectée : {e}")
            logging.error(f"Déconnexion détectée : {e}")
            if channel:
                await channel.send(f"⚠️ **Perte de communication avec Arduino ({PORT_ARDUINO})**")
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            await asyncio.sleep(5)

        await asyncio.sleep(READ_INTERVAL)


# -------------------------------------------------------------
# 🤖 Commandes Discord
# -------------------------------------------------------------
@client.event
async def on_message(message):
    global ser
    if message.author == client.user:
        return
    if message.channel.name != CHANNEL_NAME:
        return

    cmd = message.content.strip().upper()

    # --- HELP ---
    if cmd == "HELP":
        await message.channel.send(
            "🤖 **Commandes disponibles :**\n"
            "🕹️ **Rover :** `AVANCE`, `RECULE`, `GAUCHE`, `DROITE`, `STOP`\n"
            "🎥 **Caméra :** `CAM GAUCHE`, `CAM CENTRE`, `CAM DROITE`, `CAM HAUT`, `CAM BAS`\n"
            "📡 **Système :** `STATUS`, `MAP`, `UPDATE`, `REBOOT`, `DEBUG USB`, `PORTS`\n"
            f"🧭 **Télémétrie :** toutes les {int(SEND_INTERVAL/60)} min ou si variation > {SEUIL_DIST} cm\n"
            "💬 **Exemple :** `AVANCE` ou `CAM GAUCHE`\n"
        )
        return

    # --- PORTS ---
    if cmd == "PORTS":
        ports = serial.tools.list_ports.comports()
        if ports:
            msg = "**Ports détectés :**\n" + "\n".join([f"🔌 `{p.device}` → {p.description}" for p in ports])
        else:
            msg = "⚠️ Aucun port série détecté."
        await message.channel.send(msg)
        return

    # --- Commandes mouvement / caméra ---
    mouvement = {"AVANCE": "F", "RECULE": "B", "GAUCHE": "L", "DROITE": "R", "STOP": "S"}
    servo = {"CAM GAUCHE": "1", "CAM CENTRE": "2", "CAM DROITE": "3", "CAM HAUT": "U", "CAM BAS": "D"}

    if cmd in mouvement or cmd in servo:
        code = mouvement.get(cmd) or servo.get(cmd)
        if ser and ser.is_open:
            try:
                ser.write((code + "\n").encode())
                await message.channel.send(f"✅ Commande envoyée à l’Arduino : `{cmd}` → `{code}`")
            except (serial.SerialException, OSError) as e:
                await message.channel.send(f"⚠️ Erreur d'envoi : {e}")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
        else:
            await message.channel.send("⚠️ Arduino non connecté.")
        return

    # --- STATUS Raspberry Pi ---
    if cmd == "STATUS":
        uptime = datetime.timedelta(seconds=int(time.time() - psutil.boot_time()))
        cpu_temp = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                cpu_temp = int(f.read()) / 1000.0
        except Exception:
            pass
        msg = (
            f"🤖 **État du Raspberry Pi**\n"
            f"🕒 Uptime : {uptime}\n"
            f"🌡 Température CPU : {cpu_temp:.1f}°C\n"
            f"⚙️ Charge CPU : {psutil.cpu_percent()}%\n"
            f"💾 RAM utilisée : {psutil.virtual_memory().percent}%"
        )
        await message.channel.send(msg)
        return

    # --- DEBUG USB ---
    if cmd == "DEBUG USB":
        try:
            output = subprocess.check_output("dmesg | tail -10", shell=True, text=True)
            await message.channel.send(f"🧩 **Derniers logs USB :**\n```{output}```")
        except Exception as e:
            await message.channel.send(f"⚠️ Erreur lecture logs : {e}")
        return

    # --- REBOOT ---
    if cmd == "REBOOT":
        await message.channel.send("🔄 Redémarrage du Pi...")
        os.system("sudo reboot")
        return


# -------------------------------------------------------------
# 🚀 Lancement du bot
# -------------------------------------------------------------
@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")
    await client.change_presence(activity=discord.Game("Rover prêt 🚗"))
    asyncio.get_event_loop().create_task(serial_reader())


def run_discord_bot():
    client.run(TOKEN)


if __name__ == "__main__":
    run_discord_bot()

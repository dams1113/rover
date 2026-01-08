import os
import re
import discord
import subprocess
import datetime
import psutil
import time
import asyncio
import serial
import logging
from aiohttp import web

# -------------------------------------------------------------
# ⚙️ CONFIGURATION GÉNÉRALE
# -------------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()
CHANNEL_NAME = "communication-rover"   # nom du salon Discord

PORT_ARDUINO = "/dev/arduino"          # port fixe (défini via règle UDEV)
BAUDRATE_ARDUINO = 9600

READ_INTERVAL = 10.0                   # lecture série (secondes)
SEND_INTERVAL = 3600                   # intervalle max entre 2 envois (secondes)
SEUIL_DIST = 1.0                       # tolérance variation distance (cm)
SEUIL_BAT = 1.0                        # tolérance variation batterie (%)

LOG_PATH = "/home/rover/rover/rover_serial.log"

# API locale (ai_rover -> bot)
LOCAL_API_HOST = "127.0.0.1"
LOCAL_API_PORT = 5055
LOCAL_API_TOKEN = os.getenv("ROVER_LOCAL_TOKEN") or "local-change-moi-12345"

# -------------------------------------------------------------
# 🧾 LOGGING
# -------------------------------------------------------------
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# -------------------------------------------------------------
# 🤖 Discord client
# -------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# -------------------------------------------------------------
# 🔌 Connexion série Arduino
# -------------------------------------------------------------
ser = None
last_line = ""
last_sent_time = 0

# lock async pour éviter 2 writes en même temps (Discord + API locale)
serial_lock = asyncio.Lock()


def connect_arduino():
    """Initialise la connexion série à l’Arduino via port fixe /dev/arduino."""
    global ser
    try:
        ser = serial.Serial(PORT_ARDUINO, BAUDRATE_ARDUINO, timeout=1)
        # Empêche le reset automatique du CH340
        try:
            ser.dtr = False
            ser.rts = False
        except Exception:
            pass

        time.sleep(0.5)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        print(f"[SERIAL] ✅ Connecté à {PORT_ARDUINO}")
        logging.info(f"Connexion initiale à {PORT_ARDUINO}")
        return True

    except Exception as e:
        print(f"[SERIAL] ❌ Erreur de connexion Arduino : {e}")
        logging.error(f"Erreur connexion initiale : {e}")
        ser = None
        return False


async def serial_write(code: str) -> bool:
    """Ecrit une commande (1 lettre / code) sur le port série de façon safe."""
    global ser
    if ser is None or not ser.is_open:
        return False

    try:
        async with serial_lock:
            ser.write_timeout = 2
            # flushInput/flushOutput peuvent être lourds ; on évite si possible
            ser.write((code + "\n").encode())
        return True
    except Exception as e:
        logging.error(f"Erreur écriture série : {e}")
        try:
            ser.close()
        except Exception:
            pass
        ser = None
        return False


# -------------------------------------------------------------
# 🔁 Lecture série asynchrone
# -------------------------------------------------------------
async def serial_reader():
    """Lit les données série Arduino et gère les reconnections automatiques."""
    global ser, last_line, last_sent_time

    await client.wait_until_ready()
    channel = discord.utils.get(client.get_all_channels(), name=CHANNEL_NAME)

    while not client.is_closed():
        try:
            # tentative de reconnexion
            if ser is None or not ser.is_open:
                if connect_arduino():
                    if channel:
                        await channel.send(f"♻️ **Arduino connecté sur {PORT_ARDUINO}** ✅")
                else:
                    await asyncio.sleep(5)
                    continue

            # lecture série
            if ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    await asyncio.sleep(READ_INTERVAL)
                    continue

                print(f"[SERIAL] {line}")
                logging.info(f"Lecture série : {line}")

                # messages de commande
                if line.startswith("CMD:") and channel:
                    await channel.send(f"🖥️ **Arduino →** `{line}`")

                # --- TÉLÉMÉTRIE ---
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
                        if bat:
                            msg += f"🔋 Batterie : `{bat.group(1)}`\n"
                        if dist:
                            msg += f"📏 Distance : `{dist.group(1)}`\n"
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
                if ser:
                    ser.close()
            except Exception:
                pass
            ser = None
            await asyncio.sleep(1)

        await asyncio.sleep(READ_INTERVAL)


# -------------------------------------------------------------
# 🌐 API locale pour le pilotage moteur (ai_rover -> bot)
# -------------------------------------------------------------
async def motor_handler(request: web.Request):
    token = request.headers.get("X-ROVER-LOCAL-TOKEN", "")
    if token != LOCAL_API_TOKEN:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad_json"}, status=400)

    cmd = (data.get("cmd") or "").upper().strip()

    mapping = {
        "FORWARD": "F",
        "BACK": "B",
        "LEFT": "L",
        "RIGHT": "R",
        "STOP": "S",
        "F": "F", "B": "B", "L": "L", "R": "R", "S": "S"
    }

    if cmd not in mapping:
        return web.json_response({"ok": False, "error": "bad_cmd"}, status=400)

    if ser is None or not ser.is_open:
        return web.json_response({"ok": False, "error": "arduino_not_connected"}, status=503)

    code = mapping[cmd]
    sent = await serial_write(code)
    if not sent:
        return web.json_response({"ok": False, "error": "serial_write_failed"}, status=500)

    return web.json_response({"ok": True, "sent": True, "code": code})


async def start_local_api():
    app = web.Application()
    app.router.add_post("/motor", motor_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, LOCAL_API_HOST, LOCAL_API_PORT)
    await site.start()

    print(f"[LOCAL_API] ✅ http://{LOCAL_API_HOST}:{LOCAL_API_PORT}/motor")
    logging.info(f"Local API started on {LOCAL_API_HOST}:{LOCAL_API_PORT}")


# -------------------------------------------------------------
# 💬 Commandes Discord
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
            "📡 **Système :** `STATUS`, `MAP`, `UPDATE`, `REBOOT`, `DEBUG USB`\n"
            f"🧭 **Télémétrie :** toutes les {int(SEND_INTERVAL/60)} min ou si variation > {SEUIL_DIST} cm\n"
        )
        return

    mouvement = {"AVANCE": "F", "RECULE": "B", "GAUCHE": "L", "DROITE": "R", "STOP": "S"}
    servo = {"CAM GAUCHE": "1", "CAM CENTRE": "2", "CAM DROITE": "3", "CAM HAUT": "U", "CAM BAS": "D"}

    if cmd in mouvement or cmd in servo:
        code = mouvement.get(cmd) or servo.get(cmd)
        if ser and ser.is_open:
            sent = await serial_write(code)
            if sent:
                await message.channel.send(f"✅ Commande envoyée à l’Arduino : `{cmd}` → `{code}`")
            else:
                await message.channel.send("⚠️ Erreur d'envoi (série). Tentative de reconnexion…")
                connect_arduino()
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

    loop = asyncio.get_event_loop()
    loop.create_task(serial_reader())
    loop.create_task(start_local_api())


def run_discord_bot():
    client.run(TOKEN)


if __name__ == "__main__":
    run_discord_bot()

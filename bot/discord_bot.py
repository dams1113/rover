import os
import re
import time
import asyncio
import logging
import datetime
import subprocess

import discord
import psutil
import serial

from aiohttp import web

# -------------------------------------------------------------
# ⚙️ CONFIGURATION
# -------------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()
CHANNEL_NAME = "communication-rover"

PORT_ARDUINO = "/dev/arduino"
BAUDRATE_ARDUINO = 9600

READ_INTERVAL = 10.0        # lecture série (s)
SEND_INTERVAL = 3600        # envoi max (s)
SEUIL_DIST = 1.0            # cm
SEUIL_BAT = 1.0             # %

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

def log(msg: str):
    print(msg, flush=True)
    logging.info(msg)

# -------------------------------------------------------------
# 🤖 DISCORD
# -------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# -------------------------------------------------------------
# 🔌 SERIAL
# -------------------------------------------------------------
ser = None
serial_lock = asyncio.Lock()

last_line = ""
last_sent_time = 0


def connect_arduino() -> bool:
    """(Re)connecte l'Arduino."""
    global ser
    try:
        # ferme proprement si déjà ouvert
        try:
            if ser and ser.is_open:
                ser.close()
        except Exception:
            pass

        ser = serial.Serial(PORT_ARDUINO, BAUDRATE_ARDUINO, timeout=1)

        # Evite reset auto (CH340)
        try:
            ser.dtr = False
            ser.rts = False
        except Exception:
            pass

        time.sleep(0.3)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        log(f"[SERIAL] ✅ Connecté à {PORT_ARDUINO}")
        return True

    except Exception as e:
        ser = None
        log(f"[SERIAL] ❌ Erreur connexion : {e}")
        return False


async def serial_write(code: str) -> bool:
    """Ecrit sur le port série de façon thread-safe (async lock)."""
    global ser
    if ser is None or not ser.is_open:
        return False

    try:
        async with serial_lock:
            ser.write_timeout = 1
            ser.write((code + "\n").encode())
        return True
    except Exception as e:
        log(f"[SERIAL] ⚠️ write failed ({code}) : {e}")
        try:
            ser.close()
        except Exception:
            pass
        ser = None
        return False


async def serial_write_robust(code: str, retry: int = 2) -> tuple[bool, str]:
    """
    Ecriture robuste :
    - si port fermé -> reconnect
    - si write échoue -> reconnect et retry
    """
    global ser

    # 1) assure une connexion
    if ser is None or not ser.is_open:
        if not connect_arduino():
            return False, "not_connected"

    # 2) essais
    for i in range(retry + 1):
        ok = await serial_write(code)
        if ok:
            if i == 0:
                return True, "ok"
            return True, f"ok_retry_{i}"

        # si write échoue, on tente une reconnexion puis on retente
        connect_arduino()
        await asyncio.sleep(0.05)

    return False, "serial_write_failed"


# -------------------------------------------------------------
# 🔁 SERIAL READER (telemetry)
# -------------------------------------------------------------
async def serial_reader():
    global ser, last_line, last_sent_time

    await client.wait_until_ready()
    channel = discord.utils.get(client.get_all_channels(), name=CHANNEL_NAME)

    while not client.is_closed():
        try:
            if ser is None or not ser.is_open:
                connect_arduino()
                await asyncio.sleep(2)
                continue

            if ser.in_waiting:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    await asyncio.sleep(READ_INTERVAL)
                    continue

                log(f"[SERIAL] {line}")

                # messages "CMD:" envoyés par Arduino
                if line.startswith("CMD:") and channel:
                    await channel.send(f"🖥️ **Arduino →** `{line}`")

                # télémétrie filtrée
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
            log(f"[SERIAL] ⚠️ Déconnexion détectée : {e}")
            try:
                if ser:
                    ser.close()
            except Exception:
                pass
            ser = None
            await asyncio.sleep(1)

        await asyncio.sleep(READ_INTERVAL)


# -------------------------------------------------------------
# 🌐 LOCAL API (ai_rover -> bot)
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
        "F": "F", "B": "B", "L": "L", "R": "R", "S": "S",
    }

    if cmd not in mapping:
        return web.json_response({"ok": False, "error": "bad_cmd"}, status=400)

    code = mapping[cmd]

    ok, note = await serial_write_robust(code, retry=2)
    if ok:
        return web.json_response({"ok": True, "sent": True, "code": code, "note": note})

    # fail-safe : si STOP échoue, on retente plus agressif
    if code == "S":
        ok2, note2 = await serial_write_robust("S", retry=5)
        if ok2:
            return web.json_response({"ok": True, "sent": True, "code": "S", "note": f"failsafe_{note2}"})

    return web.json_response({"ok": False, "error": note}, status=500)


async def start_local_api():
    app = web.Application()
    app.router.add_post("/motor", motor_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, LOCAL_API_HOST, LOCAL_API_PORT)
    await site.start()

    log(f"[LOCAL_API] ✅ http://{LOCAL_API_HOST}:{LOCAL_API_PORT}/motor")


# -------------------------------------------------------------
# 💬 DISCORD COMMANDES
# -------------------------------------------------------------
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.name != CHANNEL_NAME:
        return

    cmd = message.content.strip().upper()

    if cmd == "HELP":
        await message.channel.send(
            "🤖 **Commandes disponibles :**\n"
            "🕹️ **Rover :** `AVANCE`, `RECULE`, `GAUCHE`, `DROITE`, `STOP`\n"
            "🎥 **Caméra :** `CAM GAUCHE`, `CAM CENTRE`, `CAM DROITE`, `CAM HAUT`, `CAM BAS`\n"
            "📡 **Système :** `STATUS`, `DEBUG USB`, `REBOOT`\n"
        )
        return

    mouvement = {"AVANCE": "F", "RECULE": "B", "GAUCHE": "L", "DROITE": "R", "STOP": "S"}
    servo = {"CAM GAUCHE": "1", "CAM CENTRE": "2", "CAM DROITE": "3", "CAM HAUT": "U", "CAM BAS": "D"}

    if cmd in mouvement or cmd in servo:
        code = mouvement.get(cmd) or servo.get(cmd)
        ok, note = await serial_write_robust(code, retry=2)
        if ok:
            await message.channel.send(f"✅ `{cmd}` → `{code}` ({note})")
        else:
            await message.channel.send(f"⚠️ Échec `{cmd}` → `{code}` ({note})")
        return

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

    if cmd == "DEBUG USB":
        try:
            output = subprocess.check_output("dmesg | tail -20", shell=True, text=True)
            await message.channel.send(f"🧩 **Derniers logs USB :**\n```{output}```")
        except Exception as e:
            await message.channel.send(f"⚠️ Erreur lecture logs : {e}")
        return

    if cmd == "REBOOT":
        await message.channel.send("🔄 Redémarrage du Pi…")
        os.system("sudo reboot")
        return


# -------------------------------------------------------------
# 🚀 START
# -------------------------------------------------------------
@client.event
async def on_ready():
    log(f"[ROVER] ✅ Connecté en tant que {client.user}")

    # ouvre série dès le départ
    connect_arduino()

    loop = asyncio.get_event_loop()
    loop.create_task(serial_reader())
    loop.create_task(start_local_api())


def run_discord_bot():
    client.run(TOKEN)


if __name__ == "__main__":
    run_discord_bot()

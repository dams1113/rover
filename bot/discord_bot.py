import os
import re
import discord
import subprocess
import datetime
import psutil
import time
import asyncio
import serial

# --- CONFIGURATION ---
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()
CHANNEL_NAME = "communication-rover"  # salon Discord
PORT_ARDUINO = "/dev/ttyUSB0"  # Arduino (moteurs + caméra)
BAUDRATE_ARDUINO = 9600
READ_INTERVAL = 10.0            # lecture série (secondes)
SEND_INTERVAL = 3600            # délai min entre télémétries

# --- Discord ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Connexion série Arduino ---
ser = None
try:
    ser = serial.Serial(PORT_ARDUINO, BAUDRATE_ARDUINO, timeout=1)
    time.sleep(2)
    print(f"[SERIAL] ✅ Connecté à {PORT_ARDUINO}")
except Exception as e:
    print(f"[SERIAL] ❌ Erreur connexion Arduino : {e}")

last_line = ""
last_sent_time = 0

# --- PATH PYTHON ---
PYTHON_BIN = "/home/rover/rover/.venv/bin/python"

# -------- EVENTS ----------
@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")
    for guild in client.guilds:
        for ch in guild.text_channels:
            if ch.name == CHANNEL_NAME:
                print(f"[Discord] 🛰️ Connecté au salon : #{ch.name}")
    await client.change_presence(activity=discord.Game("Rover prêt 🚗"))
    asyncio.get_event_loop().create_task(serial_reader())


# -------- LECTURE SÉRIE --------
async def serial_reader():
    """Lit les données série de l’Arduino et les publie dans Discord sans spam."""
    global last_line, last_sent_time

    await client.wait_until_ready()
    channel = discord.utils.get(client.get_all_channels(), name=CHANNEL_NAME)

    while not client.is_closed():
        if ser and ser.in_waiting:
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    await asyncio.sleep(READ_INTERVAL)
                    continue

                # affichage console
                print(f"[SERIAL] {line}")

                # réponse directe Arduino (cmd: ...)
                if line.startswith("CMD:") and channel:
                    await channel.send(f"🖥️ **Arduino →** `{line}`")

                # Télémétrie (BAT / DIST / IR)
                if "BAT:" in line:
                    now = time.time()
                    if line != last_line or (now - last_sent_time) > SEND_INTERVAL:
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
            except Exception as e:
                print(f"[SERIAL] ⚠️ Erreur lecture : {e}")
        await asyncio.sleep(READ_INTERVAL)


# -------- COMMANDES DISCORD --------
@client.event
async def on_message(message):
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
            "📡 **Système :** `STATUS`, `MAP`, `UPDATE`, `REBOOT`, `GOTO lat lon`\n"
            "🧭 **Infos :** Télémétrie automatique toutes les 30 s ou si changement\n"
            "💬 **Exemple :** `AVANCE` ou `CAM GAUCHE`\n"
        )
        return

    # --- Commandes rover ---
    mouvement = {
        "AVANCE": "F",
        "RECULE": "B",
        "GAUCHE": "L",
        "DROITE": "R",
        "STOP": "S",
    }

    # --- Commandes caméra ---
    servo = {
        "CAM GAUCHE": "1",
        "CAM CENTRE": "2",
        "CAM DROITE": "3",
        "CAM HAUT": "U",
        "CAM BAS": "D",
    }

    # --- Exécution des commandes Arduino ---
    if cmd in mouvement or cmd in servo:
        code = mouvement.get(cmd) or servo.get(cmd)
        if ser:
            ser.write((code + "\n").encode())
            await message.channel.send(f"✅ Commande envoyée à l’Arduino : `{cmd}` → `{code}`")
        else:
            await message.channel.send("⚠️ Arduino non connecté.")
        return

    # --- STATUS Pi ---
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

    # --- MAP ---
    if cmd == "MAP":
        await message.channel.send("🛰️ Génération de la carte...")
        try:
            subprocess.run([
                PYTHON_BIN, "tools/multi_map.py",
                "--out", "map/multi_map.html",
                "--basemap", "positron",
                "--heatmap", "--points",
                "--in", f"logs/gps_{datetime.date.today()}.csv"
            ], check=True)
            await message.channel.send("✅ Carte générée : `map/multi_map.html`")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"⚠️ Erreur génération carte : {e}")
        return

    # --- UPDATE ---
    if cmd == "UPDATE":
        await message.channel.send("📡 Mise à jour en cours...")
        try:
            subprocess.run(["bash", "git_update.sh"], check=True)
            await message.channel.send("✅ Mise à jour terminée.")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"⚠️ Erreur update : {e}")
        return

    # --- REBOOT ---
    if cmd == "REBOOT":
        await message.channel.send("🔄 Redémarrage du Pi...")
        os.system("sudo reboot")
        return

    # --- GOTO GPS ---
    if cmd.startswith("GOTO"):
        try:
            parts = cmd.split()
            if len(parts) >= 3:
                lat = float(parts[1])
                lon = float(parts[2])
                await message.channel.send(f"🧭 Navigation vers {lat}, {lon}")
                from modules import navigation
                success = navigation.goto(lat, lon)
                await message.channel.send("✅ Objectif atteint !" if success else "⚠️ Navigation interrompue")
            else:
                await message.channel.send("❌ Utilisation : `GOTO lat lon`")
        except ValueError:
            await message.channel.send("❌ Format invalide pour `GOTO`.")
        return


# -------- Lancement --------
def run_discord_bot():
    client.run(TOKEN)

if __name__ == "__main__":
    run_discord_bot()

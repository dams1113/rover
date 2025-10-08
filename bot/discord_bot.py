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
PORT = "/dev/ttyUSB0"          # ⚠️ adapte si besoin (/dev/ttyACM0)
BAUDRATE = 9600                # même valeur que Serial.begin sur l’Arduino
CHANNEL_NAME = "rover-server"  # nom exact du salon Discord
READ_INTERVAL = 2              # lecture série toutes les 2 s
SEND_INTERVAL = 30             # envoi Discord max toutes les 30 s

# --- Discord ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Connexion série ---
ser = None
try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    time.sleep(2)
    print(f"[SERIAL] ✅ Connecté à {PORT}")
except Exception as e:
    print(f"[SERIAL] ❌ Erreur connexion série : {e}")

# --- Variables globales ---
last_telemetry = ""
last_sent_time = 0

# --- Chemin Python (venv) ---
PYTHON_BIN = "/home/rover/rover/.venv/bin/python"

# -------- EVENTS ----------
@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté à Discord en tant que {client.user}")
    for guild in client.guilds:
        for ch in guild.text_channels:
            if ch.name == CHANNEL_NAME:
                print(f"[Discord] 🛰️ Connecté au salon : #{ch.name}")
    await client.change_presence(activity=discord.Game("Mode complet actif"))
    asyncio.get_event_loop().create_task(serial_reader())


# -------- LECTURE SÉRIE --------
async def serial_reader():
    """Lit les données série Arduino et envoie sur Discord sans spam."""
    global last_telemetry, last_sent_time
    await client.wait_until_ready()
    channel = discord.utils.get(client.get_all_channels(), name=CHANNEL_NAME)

    while not client.is_closed():
        if ser and ser.in_waiting:
            try:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    await asyncio.sleep(READ_INTERVAL)
                    continue

                clean_line = line.encode('ascii', 'ignore').decode().strip()
                now = time.time()

                if clean_line != last_telemetry or (now - last_sent_time) > SEND_INTERVAL:
                    last_telemetry = clean_line
                    last_sent_time = now

                    # Parsing des données BAT, DIST, IR
                    bat = re.search(r"BAT[:=]\s*([\d\.]+%?|[\d\.]+V)", clean_line)
                    dist = re.search(r"DIST[:=]\s*([\d\.]+cm?)", clean_line)
                    ir_l = re.search(r"IR_L[:=]\s*(\d)", clean_line)
                    ir_r = re.search(r"IR_R[:=]\s*(\d)", clean_line)

                    msg = "📡 **Télémétrie Arduino**\n"
                    if bat:  msg += f"🔋 Batterie : `{bat.group(1)}`\n"
                    if dist: msg += f"📏 Distance : `{dist.group(1)}`\n"
                    if ir_l and ir_r:
                        msg += f"👁️ IR Gauche : `{ir_l.group(1)}` | Droite : `{ir_r.group(1)}`"

                    print(f"[SERIAL] {clean_line}")
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

    cmd = message.content.strip().upper()
    if not cmd or message.channel.name != CHANNEL_NAME:
        return

    # --- Aide ---
    if cmd == "HELP":
        await message.channel.send(
            "🤖 **Commandes disponibles :**\n"
            "🕹️ `AVANCE`, `RECULE`, `GAUCHE`, `DROITE`, `STOP`\n"
            "🎥 `CAM GAUCHE`, `CAM CENTRE`, `CAM DROITE`, `CAM HAUT`, `CAM BAS`\n"
            "🛰️ `STATUS`, `MAP`, `UPDATE`, `REBOOT`, `GOTO lat lon`\n"
            "_Télémétrie envoyée si changement ou toutes les 30 s._"
        )
        return

    # --- Commandes moteur ---
    mouvement = {
        "AVANCE": "F",
        "RECULE": "B",
        "GAUCHE": "L",
        "DROITE": "R",
        "STOP": "S"
    }

    # --- Commandes servo caméra ---
    servo = {
        "CAM GAUCHE": "1",
        "CAM CENTRE": "2",
        "CAM DROITE": "3",
        "CAM HAUT": "U",
        "CAM BAS": "D"
    }

    # --- Actions série ---
    if cmd in mouvement:
        if ser:
            ser.write((mouvement[cmd] + "\n").encode())
            print(f"[SERIAL] → {mouvement[cmd]}")
        await message.channel.send(f"🚗 Commande envoyée : `{cmd}` ➜ `{mouvement[cmd]}`")
        return

    if cmd in servo:
        if ser:
            ser.write((servo[cmd] + "\n").encode())
            print(f"[SERIAL] → {servo[cmd]}")
        await message.channel.send(f"🎥 Caméra : `{cmd}` ➜ `{servo[cmd]}`")
        return

    # --- STATUS (système Pi) ---
    if cmd == "STATUS":
        uptime = datetime.timedelta(seconds=int(time.time() - psutil.boot_time()))
        cpu_temp = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                cpu_temp = int(f.read()) / 1000.0
        except Exception:
            pass
        msg = (
            f"🤖 **État du Pi**\n"
            f"🕒 Uptime : {uptime}\n"
            f"🌡 Température CPU : {cpu_temp:.1f}°C"
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
            await message.channel.send(f"⚠️ Erreur carte : {e}")
        return

    # --- UPDATE ---
    if cmd == "UPDATE":
        await message.channel.send("📡 Mise à jour du code...")
        try:
            subprocess.run(["bash", "git_update.sh"], check=True)
            await message.channel.send("✅ Mise à jour terminée.")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"⚠️ Erreur update : {e}")
        return

    # --- REBOOT ---
    if cmd == "REBOOT":
        await message.channel.send("🔄 Redémarrage du Raspberry Pi...")
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
                await message.channel.send("❌ Utilisation: `GOTO lat lon`")
        except ValueError:
            await message.channel.send("❌ Format invalide pour GOTO")
        return


# -------- Lancement --------
def run_discord_bot():
    client.run(TOKEN)

if __name__ == "__main__":
    run_discord_bot()

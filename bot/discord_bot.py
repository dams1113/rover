import discord
import asyncio
import os
import subprocess
import psutil
import pathlib
from datetime import datetime, timedelta

from modules.energie import get_battery_status as get_power_status
from modules.gps_reader import get_gps_data, start_gps_loop
from modules.motors import handle_movement

# Lire le token depuis un fichier sécurisé
with open("bot/token.txt", "r") as f:
    TOKEN = f.read().strip()

# ID du salon Discord
CHANNEL_ID = 1398325400475537462  # ⚠️ adapte si besoin

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Début de session
start_time = datetime.now()

# Historique tension/courant
last_voltages = []
last_currents = []

# Dernière session (chargée depuis un fichier)
SESSION_FILE = "bot/last_session.txt"


# --- Fonctions utilitaires ---
def get_git_commit_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except:
        return "inconnu"

def get_cpu_temperature():
    try:
        out = subprocess.check_output("cat /sys/class/thermal/thermal_zone0/temp", shell=True, text=True)
        return round(int(out) / 1000, 1)
    except:
        return "N/A"

def get_uptime():
    return datetime.now() - start_time

def load_last_session_duration():
    try:
        with open(SESSION_FILE, "r") as f:
            seconds = float(f.read().strip())
            return timedelta(seconds=seconds)
    except:
        return "Inconnue"

def save_current_session_duration():
    duration = (datetime.now() - start_time).total_seconds()
    with open(SESSION_FILE, "w") as f:
        f.write(str(duration))


# --- Événements Discord ---
@client.event
async def on_ready():
    print(f"[Rover] Connecté en tant que {client.user}")
    # Lancer la boucle GPS
    start_gps_loop()


@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    cmd = message.content.strip().upper()

    # --- STATUS ---
    if cmd == "STATUS":
        uptime = get_uptime()
        power = get_power_status()
        voltage = power.get("voltage", "N/A")
        current = power.get("current", "N/A")

        last_voltages.append(voltage)
        last_currents.append(current)

        gps = get_gps_data()
        if "error" in gps:
            gps_str = f"📍 GPS : {gps['error']}"
        else:
            gps_str = f"📍 GPS : {gps['latitude']}, {gps['longitude']} (sats={gps['satellites']})"

        msg = (
            f"🤖 Rover en ligne\n"
            f"⏱ Uptime : {uptime}\n"
            f"🔋 Tension : {voltage} V | Courant : {current} A\n"
            f"{gps_str}\n"
            f"🌡 Temp CPU : {get_cpu_temperature()} °C\n"
            f"📦 Version Git : {get_git_commit_hash()}"
        )
        await message.channel.send(msg)

    # --- UPDATE ---
    elif cmd == "UPDATE":
        await message.channel.send("⬇️ Mise à jour du code...")
        subprocess.run(["bash", "git_update.sh"])
        await message.channel.send("✅ Update terminée (sans reboot).")

    # --- REBOOT ---
    elif cmd == "REBOOT":
        await message.channel.send("♻️ Reboot en cours…")
        save_current_session_duration()
        subprocess.run(["sudo", "reboot"])

    # --- MAP ---
    elif cmd == "MAP":
        await message.channel.send("🛰️ Génération de la carte...")
        map_path = pathlib.Path("map/multi_map.html")
        map_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Prendre tous les fichiers logs/gps_*.csv
            csv_files = list(pathlib.Path("logs").glob("gps_*.csv"))
            if not csv_files:
                await message.channel.send("⚠️ Aucun fichier GPS trouvé dans logs/")
                return

            cmd_line = [
                "python3", "tools/multi_map.py",
                "--out", str(map_path),
                "--basemap", "positron",
                "--heatmap", "--points"
            ]
            for f in csv_files:
                cmd_line.extend(["--in", str(f)])

            subprocess.run(cmd_line, check=True)
            await message.channel.send(file=discord.File(str(map_path)))

        except Exception as e:
            await message.channel.send(f"⚠️ Erreur génération carte : {e}")

    # --- Commandes moteurs (exemple) ---
    elif cmd in ["AVANCE", "RECULE", "GAUCHE", "DROITE", "STOP"]:
        await message.channel.send(f"🕹 Commande mouvement : {cmd}")
        handle_movement(cmd)


# --- Lancer le bot ---
client.run(TOKEN)

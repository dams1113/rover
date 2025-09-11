# bot/discord_bot.py
import discord
import asyncio
import os
import subprocess
import psutil
import pathlib
from datetime import datetime, timedelta

from modules.energie import get_battery_status as get_power_status
from modules.gps_reader import get_gps_data as get_gps_position
from modules.motors import handle_movement

# Lire le token depuis un fichier sécurisé
with open("bot/token.txt", "r") as f:
    TOKEN = f.read().strip()

# ID du salon Discord
CHANNEL_ID = 1398325400475537462  # ⚠️ adapte avec ton ID réel

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Début de session
start_time = datetime.now()

# Historique
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
    print(f"[ROVER] Connecté en tant que {client.user}")
    commit = get_git_commit_hash()
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"✅ Rover en ligne – version `{commit}`")


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

        gps = get_gps_position()
        if "error" in gps:
            gps_str = f"📍 GPS : {gps['error']}"
        else:
            ts = gps.get("timestamp")
            if ts:
                try:
                    ts_dt = datetime.fromisoformat(ts)
                    age = (datetime.utcnow() - ts_dt).total_seconds()
                except Exception:
                    age = None

                if age is not None and age > 30:
                    gps_str = f"📍 GPS : {gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m - {gps['satellites']} sats\n⚠️ Données GPS vieilles de {int(age)}s"
                else:
                    gps_str = f"📍 GPS : {gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m - {gps['satellites']} sats\n🕔 Dernière fix : {ts}"
            else:
                gps_str = "📍 GPS : pas de timestamp"

        avg_voltage = round(sum(last_voltages) / len(last_voltages), 2) if last_voltages else "N/A"
        avg_current = round(sum(last_currents) / len(last_currents), 2) if last_currents else "N/A"

        temp_cpu = get_cpu_temperature()
        cpu_percent = psutil.cpu_percent(interval=1)
        last_session = load_last_session_duration()

        response = f"""🤖 **État du Rover**
🔋 Tension actuelle : {voltage} V
🔌 Courant actuel : {current} A
🕒 Durée depuis allumage : {uptime}
⏱ Dernière session : {last_session}
📊 Moyenne : {avg_voltage}V / {avg_current}A
🌡 Température CPU : {temp_cpu}°C
🧠 CPU utilisé : {cpu_percent}%
{gps_str}
"""
        await message.channel.send(response)

    # --- Commandes moteurs ---
    elif cmd in ["AVANCE", "RECULE", "STOP"]:
        handle_movement(cmd)
        await message.channel.send(f"[ROVER] Commande reçue : {cmd}")

    # --- REBOOT ---
    elif cmd == "REBOOT":
        await message.channel.send("🔄 Redémarrage du Rover...")
        save_current_session_duration()
        await asyncio.sleep(2)
        os.system("sudo reboot")

    # --- UPDATE ---
    elif cmd == "UPDATE":
        await message.channel.send("🔄 Mise à jour en cours...")
        try:
            result = subprocess.run(
                ["/home/rover/rover/git_update.sh"],
                capture_output=True,
                text=True,
                check=False
            )
            stdout = result.stdout.strip()
            if len(stdout) > 1900:
                stdout = stdout[:1900] + "\n[...] (tronqué)"

            if result.returncode == 0:
                await message.channel.send(f"✅ Mise à jour terminée :\n```{stdout}```")
            else:
                await message.channel.send(f"❌ Échec de la mise à jour :\n```{result.stderr.strip()}```")

        except Exception as e:
            await message.channel.send(f"❌ Erreur lors de la mise à jour : {e}")

    # --- MAP ---
    elif cmd == "MAP":
        await message.channel.send("🛰️ Génération de la carte...")
        map_path = pathlib.Path("map/multi_map.html")
        map_path.parent.mkdir(parents=True, exist_ok=True)

        try:
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


# --- Lancer le bot ---
client.run(TOKEN)

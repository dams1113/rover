import discord
import asyncio
import os
import subprocess
import psutil
from datetime import datetime, timedelta
from modules.energie import get_battery_status as get_power_status
from modules.gps_reader import get_gps_data as get_gps_position
from modules.motors import handle_movement

# Token
with open("bot/token.txt", "r") as f:
    TOKEN = f.read().strip()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Variables de mission
start_time = datetime.now()
last_mission_start = None
last_mission_end = None
last_voltages = []
last_currents = []

CHANNEL_ID = None 



@client.event
async def on_ready():
    print(f"[ROVER] Connecté en tant que {client.user}")
    channel = client.get_channel(CHANNEL_ID)

    # Récupération du commit git
    try:
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(__file__) + "/.."
        ).decode("utf-8").strip()
    except Exception:
        commit_hash = "inconnu"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"👋 Rover en ligne sur `main@{commit_hash}` – démarré le {now}"
    if channel:
        await channel.send(message)

@client.event
async def on_message(message):
    global last_mission_start, last_mission_end

    if message.author == client.user or message.channel.id != CHANNEL_ID:
        return

    cmd = message.content.strip().upper()

    if cmd == "STATUS":
        uptime = datetime.now() - start_time
        power = get_power_status()
        voltage = power.get("voltage", "N/A")
        current = power.get("current", "N/A")

        last_voltages.append(voltage)
        last_currents.append(current)

        avg_voltage = round(sum(last_voltages) / len(last_voltages), 2) if last_voltages else "N/A"
        avg_current = round(sum(last_currents) / len(last_currents), 2) if last_currents else "N/A"

        gps = get_gps_position()
        gps_str = f"📍 GPS : {gps['error']}" if "error" in gps else f"📍 GPS : {gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m - {gps['satellites']} sats"

        mission_duration = (
            last_mission_end - last_mission_start if last_mission_start and last_mission_end else "N/A"
        )

        # CPU temp & usage
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = round(int(f.read()) / 1000, 1)
        except Exception:
            temp = "N/A"

        cpu_percent = psutil.cpu_percent(interval=1)

        response = f"""🤖 **État du Rover**
🔋 Tension actuelle : {voltage} V
🔌 Courant actuel : {current} A
📊 Moyenne : {avg_voltage}V / {avg_current}A
🌡️ Température CPU : {temp}°C
🧠 Utilisation CPU : {cpu_percent}%
🕒 Uptime : {str(uptime).split('.')[0]}
🚗 Dernière mission : {mission_duration}
{gps_str}
"""
        await message.channel.send(response)

    elif cmd in ["AVANCE", "RECULE", "STOP"]:
        last_mission_start = datetime.now()
        handle_movement(cmd)
        await message.channel.send(f"[ROVER] Commande reçue : {cmd}")
        last_mission_end = datetime.now()

    elif cmd == "REBOOT":
        await message.channel.send("🔄 Redémarrage du Rover...")
        await asyncio.sleep(2)
        os.system("sudo reboot")

    elif cmd == "UPDATE":
        await message.channel.send("📡 Mise à jour en cours via Git...")
        try:
            result = subprocess.check_output("cd ~/rover && git pull", shell=True, stderr=subprocess.STDOUT, text=True)
            await message.channel.send(f"✅ Mise à jour terminée :\n```{result}```")
            await message.channel.send("🔄 Redémarrage du Rover...")
            await asyncio.sleep(2)
            os.system("sudo reboot")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"❌ Erreur lors du `git pull` :\n```{e.output}```")

# Lancement du bot
def run():
    client.run(TOKEN)

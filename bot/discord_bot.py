import discord
import asyncio
import os
import subprocess
import psutil
from datetime import datetime, timedelta
from modules.energie import (
    get_battery_status as get_power_status,
    get_power_estimate
)
from modules.gps_reader import get_gps_data as get_gps_position
from modules.motors import handle_movement

# Token
with open("bot/token.txt", "r") as f:
    TOKEN = f.read().strip()

CHANNEL_ID = 1398325400475537462  # Ton ID de salon Discord

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

start_time = datetime.now()
last_mission_start = None
last_mission_end = None
last_voltages = []
last_currents = []

BOOT_TIME_FILE = "last_shutdown.txt"

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

def get_last_session_duration():
    if not os.path.exists(BOOT_TIME_FILE):
        return "Inconnue"
    try:
        with open(BOOT_TIME_FILE, "r") as f:
            last_shutdown_str = f.read().strip()
        last_shutdown = datetime.fromisoformat(last_shutdown_str)
        return str(timedelta(seconds=int((last_shutdown - last_boot_time).total_seconds())))
    except:
        return "Inconnue"

@client.event
async def on_ready():
    print(f"[ROVER] Connecté en tant que {client.user}")
    global last_boot_time
    last_boot_time = datetime.now()
    commit = get_git_commit_hash()
    session_duration = get_last_session_duration()
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"✅ Rover en ligne – version `{commit}`\n⏱ Dernière session : {session_duration}")

@client.event
async def on_message(message):
    global last_mission_start, last_mission_end

    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    cmd = message.content.strip().upper()

    if cmd == "STATUS":
        uptime = datetime.now() - start_time
        power = get_power_status()
        voltage = power.get("voltage", "N/A")
        current = power.get("current", "N/A")

        last_voltages.append(voltage)
        last_currents.append(current)

        gps = get_gps_position()
        gps_str = f"📍 GPS : {gps['error']}" if "error" in gps else f"📍 GPS : {gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m - {gps['satellites']} sats"

        mission_duration = (
            str(last_mission_end - last_mission_start)
            if last_mission_start and last_mission_end else "N/A"
        )

        avg_voltage = round(sum(last_voltages) / len(last_voltages), 2) if last_voltages else "N/A"
        avg_current = round(sum(last_currents) / len(last_currents), 2) if last_currents else "N/A"
        temp_cpu = get_cpu_temperature()
        cpu_percent = psutil.cpu_percent(interval=1)
        power_watt = get_power_estimate()

        response = f"""🤖 **État du Rover**
🔋 Tension actuelle : {voltage} V
🔌 Courant actuel : {current} A
⚡ Puissance estimée : {power_watt} W
🕒 Durée depuis allumage : {str(uptime).split('.')[0]}
📊 Dernière mission : {mission_duration}
🔋 Moyenne : {avg_voltage}V / {avg_current}A
🌡 Température CPU : {temp_cpu}°C
🧠 CPU utilisé : {cpu_percent}%
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

@client.event
async def on_disconnect():
    # Sauvegarder l’heure de coupure
    with open(BOOT_TIME_FILE, "w") as f:
        f.write(datetime.now().isoformat())

def run():
    client.run(TOKEN)

import discord
import asyncio
import os
import subprocess
import psutil
from datetime import datetime
from modules.energie import get_battery_status as get_power_status
from modules.gps_reader import get_gps_data as get_gps_position
from modules.motors import handle_movement

# Lire le token
with open("bot/token.txt", "r") as f:
    TOKEN = f.read().strip()

# Remplacer par l’ID réel de ton salon
CHANNEL_ID = 1398325400475537462 # 👈 remplace-moi par ton vrai salon Discord

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

start_time = datetime.now()
last_mission_start = None
last_mission_end = None
last_voltages = []
last_currents = []

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

@client.event
async def on_ready():
    print(f"[ROVER] Connecté en tant que {client.user}")
    commit = get_git_commit_hash()
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(f"✅ Rover en ligne – version `{commit}`")

@client.event
async def on_message(message):
    global last_mission_start, last_mission_end

    print(f"[DEBUG] Message reçu : {message.content} dans salon {message.channel.id}")

    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    cmd = message.content.strip().upper()

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
            gps_str = f"📍 GPS : {gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m - {gps['satellites']} sats"

        if last_mission_start and last_mission_end:
            mission_duration = last_mission_end - last_mission_start
        else:
            mission_duration = "N/A"

        avg_voltage = round(sum(last_voltages) / len(last_voltages), 2) if last_voltages else "N/A"
        avg_current = round(sum(last_currents) / len(last_currents), 2) if last_currents else "N/A"

        temp_cpu = get_cpu_temperature()
        cpu_percent = psutil.cpu_percent(interval=1)

        response = f"""🤖 **État du Rover**
🔋 Tension actuelle : {voltage} V
🔌 Courant actuel : {current} A
🕒 Durée depuis allumage : {uptime}
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

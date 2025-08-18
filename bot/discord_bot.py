import discord
import asyncio
import os
import subprocess
from datetime import datetime
from modules.energie import get_battery_status as get_power_status
from modules.gps_reader import get_gps_data as get_gps_position
from modules.motors import handle_movement
import psutil

# Chargement du token
with open("bot/token.txt", "r") as f:
    TOKEN = f.read().strip()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

start_time = datetime.now()
last_mission_start = None
last_mission_end = None
last_voltages = []
last_currents = []

def get_cpu_temp():
    try:
        output = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        return float(output.replace("temp=", "").replace("'C\n", ""))
    except Exception:
        return "N/A"

def get_cpu_usage():
    try:
        return psutil.cpu_percent(interval=1)
    except Exception:
        return "N/A"

@client.event
async def on_ready():
    print(f"[ROVER] Connecté en tant que {client.user}")

@client.event
async def on_message(message):
    global last_mission_start, last_mission_end

    if message.author == client.user:
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
        if "error" in gps:
            gps_str = f"📍 GPS : {gps['error']}"
        else:
            gps_str = f"📍 GPS : {gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m - {gps['satellites']} sats"

        cpu_temp = get_cpu_temp()
        cpu_usage = get_cpu_usage()

        if last_mission_start and last_mission_end:
            mission_duration = last_mission_end - last_mission_start
            mission_info = f"{mission_duration} (de {last_mission_start.strftime('%H:%M:%S')} à {last_mission_end.strftime('%H:%M:%S')})"
        else:
            mission_info = "N/A"

        avg_voltage = round(sum(last_voltages) / len(last_voltages), 2) if last_voltages else "N/A"
        avg_current = round(sum(last_currents) / len(last_currents), 2) if last_currents else "N/A"

        response = f"""🤖 État du Rover
🔋 Tension actuelle : {voltage} V
🔌 Courant actuel : {current} A
🌡️ Température CPU : {cpu_temp} °C
🧠 Charge CPU : {cpu_usage} %
🕒 Dernière mission : {mission_info}
🔋 Moyenne : {avg_voltage}V / {avg_current}A
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

def run():
    client.run(TOKEN)

import discord
import asyncio
import os
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

start_time = datetime.now()
last_mission_start = None
last_mission_end = None
last_voltages = []
last_currents = []

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

        if last_mission_start and last_mission_end:
            mission_duration = last_mission_end - last_mission_start
        else:
            mission_duration = "N/A"

        avg_voltage = round(sum(last_voltages) / len(last_voltages), 2) if last_voltages else "N/A"
        avg_current = round(sum(last_currents) / len(last_currents), 2) if last_currents else "N/A"

        response = f"""🤖 État du Rover
🔋 Tension actuelle : {voltage} V
🔌 Courant actuel : {current} A
🕒 Dernière mission : {mission_duration}
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
        await asyncio.sleep(2)  # un petit délai pour laisser le message partir
        os.system("sudo reboot")

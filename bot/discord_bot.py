import discord
import asyncio
import os
from datetime import datetime, timedelta
from modules.energie import get_battery_status as get_power_status

from data.gps_reader import get_gps_position
from data.motors import handle_movement

# Chargement du token
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.txt")
with open(TOKEN_PATH, "r") as f:
    TOKEN = f.read().strip()

CHANNEL_ID = None  # Si tu veux le limiter à un salon précis, mets l’ID ici

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Suivi de mission
mission_start_time = None
mission_energy_log = []
last_mission_duration = None
last_mission_voltage_avg = None
last_mission_current_avg = None

def reset_mission_stats():
    global mission_start_time, mission_energy_log
    mission_start_time = datetime.now()
    mission_energy_log = []

def close_mission():
    global last_mission_duration, last_mission_voltage_avg, last_mission_current_avg
    if mission_start_time is None:
        return
    duration = datetime.now() - mission_start_time
    last_mission_duration = duration

    if mission_energy_log:
        voltages = [v for v, _ in mission_energy_log]
        currents = [c for _, c in mission_energy_log]
        last_mission_voltage_avg = round(sum(voltages) / len(voltages), 2)
        last_mission_current_avg = round(sum(currents) / len(currents), 2)
    else:
        last_mission_voltage_avg = "N/A"
        last_mission_current_avg = "N/A"

@client.event
async def on_ready():
    print(f"[Rover] Connecté en tant que {client.user}")

@client.event
async def on_message(message):
    global mission_start_time, mission_energy_log
    if message.author == client.user:
        return
    if CHANNEL_ID and message.channel.id != CHANNEL_ID:
        return

    cmd = message.content.strip().upper()

    if cmd == "STATUS":
        voltage, current = get_power_status()
        gps = get_gps_position()
        gps_str = gps if gps else "📍 GPS : Non disponible"
        duration_str = str(last_mission_duration) if last_mission_duration else "Inconnue"
        v_str = f"{last_mission_voltage_avg}V" if last_mission_voltage_avg else "N/A"
        c_str = f"{last_mission_current_avg}A" if last_mission_current_avg else "N/A"

        response = f"""🤖 **État du Rover**
🔋 Tension actuelle : {voltage:.2f} V
🔌 Courant actuel : {current:.2f} A
🕒 Dernière mission : {duration_str}
🔋 Moyenne : {v_str} / {c_str}
{gps_str}
"""
        await message.channel.send(response)

    elif cmd in ["AVANCE", "RECULE", "GAUCHE", "DROITE"]:
        await message.channel.send(f"▶️ Rover : {cmd.lower()}")
        handle_movement(cmd)
        reset_mission_stats()

    elif cmd == "STOP":
        await message.channel.send("⛔ Mission terminée")
        handle_movement("STOP")
        close_mission()

def run():
    client.run(TOKEN)

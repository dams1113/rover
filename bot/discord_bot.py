import os
import discord
import subprocess
import datetime
import psutil
import time

from modules.gps_reader import get_gps_data
from modules import motors
from modules import autonomy

# Charger le token
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()

# Activer les intents nécessaires
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

PYTHON_BIN = "/home/rover/rover/.venv/bin/python"

def _parse_args(parts, default_sec=2.0, default_speed=50):
    """
    Ex: ["FORWARD", "3", "70"] -> (3.0, 70)
    """
    sec = None
    spd = None
    if len(parts) >= 2:
        try:
            sec = float(parts[1])
        except:
            sec = default_sec
    if len(parts) >= 3:
        try:
            spd = int(parts[2])
        except:
            spd = default_speed
    return sec or default_sec, spd or default_speed

@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    raw = message.content.strip()
    if not raw:
        return

    parts = raw.split()
    cmd = parts[0].upper()

    # ---- STATUS ----
    if cmd == "STATUS":
        gps = get_gps_data()
        if gps and gps.get("fix"):
            gps_str = (
                f"{gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m "
                f"- {gps['satellites']} sats\n"
                f"🕒 Fix : {gps['timestamp']}"
            )
        else:
            gps_str = "❌ Pas de fix GPS"

        uptime = datetime.timedelta(seconds=int(time.time() - psutil.boot_time()))

        cpu_temp = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                cpu_temp = int(f.read()) / 1000.0
        except Exception:
            pass

        msg = (
            "🤖 **État du Rover**\n"
            f"🕒 Uptime : {uptime}\n"
            f"🌡 Température CPU : {cpu_temp:.1f}°C\n"
            f"📍 GPS : {gps_str}\n"
        )
        await message.channel.send(msg)

    # ---- MAP ----
    elif cmd == "MAP":
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

    # ---- UPDATE ----
    elif cmd == "UPDATE":
        await message.channel.send("📡 Mise à jour en cours...")
        try:
            subprocess.run(["bash", "git_update.sh"], check=True)
            await message.channel.send("✅ Mise à jour terminée. Utilise `REBOOT` si nécessaire.")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"⚠️ Erreur update : {e}")

    # ---- REBOOT ----
    elif cmd == "REBOOT":
        await message.channel.send("🔄 Reboot du Rover...")
        os.system("sudo reboot")

    # ---- COMMANDES MOTEURS ----
    elif cmd == "FORWARD":
        sec, spd = _parse_args(parts, default_sec=2.0, default_speed=55)
        motors.forward(speed=spd, duration=sec)
        await message.channel.send(f"🚙 Avance {sec}s @ {spd}%")

    elif cmd == "BACKWARD":
        sec, spd = _parse_args(parts, default_sec=2.0, default_speed=50)
        motors.backward(speed=spd, duration=sec)
        await message.channel.send(f"↩️ Recule {sec}s @ {spd}%")

    elif cmd == "LEFT":
        sec, spd = _parse_args(parts, default_sec=1.0, default_speed=55)
        motors.turn_left(speed=spd, duration=sec)
        await message.channel.send(f"↪️ Gauche {sec}s @ {spd}%")

    elif cmd == "RIGHT":
        sec, spd = _parse_args(parts, default_sec=1.0, default_speed=55)
        motors.turn_right(speed=spd, duration=sec)
        await message.channel.send(f"↩️ Droite {sec}s @ {spd}%")

    elif cmd == "STOP":
        motors.stop()
        await message.channel.send("🛑 Stop")

    # ---- AUTONOMIE ----
    elif cmd == "AUTO":
        sub = parts[1].upper() if len(parts) > 1 else ""
        if sub == "START":
            autonomy.auto_start()
            await message.channel.send(f"🤖 Autonomie démarrée ({autonomy.auto_status()})")
        elif sub == "STOP":
            autonomy.auto_stop()
            await message.channel.send(f"🧠 Autonomie arrêtée ({autonomy.auto_status()})")
        elif sub == "STATUS":
            await message.channel.send(f"ℹ️ Autonomie: {autonomy.auto_status()}")
        else:
            await message.channel.send("Usage: `AUTO START` | `AUTO STOP` | `AUTO STATUS`")

if __name__ == "__main__":
    client.run(TOKEN)

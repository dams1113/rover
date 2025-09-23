# bot/discord_bot.py
import os
import discord
import subprocess
import datetime
import psutil
import time
from modules.gps_reader import get_gps_data

# Charger le token
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()

# Activer les intents nécessaires
intents = discord.Intents.default()
intents.message_content = True  # Obligatoire pour lire les messages
client = discord.Client(intents=intents)

PYTHON_BIN = "/home/rover/rover/.venv/bin/python"

@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    cmd = message.content.lower().strip()
    print(f"[DISCORD] Message reçu: {cmd}")  # debug log

    # ---- STATUS ----
    if cmd == "status":
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
    elif cmd == "map":
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
    elif cmd == "update":
        await message.channel.send("📡 Mise à jour en cours...")
        try:
            subprocess.run(["bash", "git_update.sh"], check=True)
            await message.channel.send("✅ Mise à jour terminée. Utilise `reboot` si nécessaire.")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"⚠️ Erreur update : {e}")

    # ---- REBOOT ----
    elif cmd == "reboot":
        await message.channel.send("🔄 Reboot du Rover...")
        os.system("sudo reboot")

if __name__ == "__main__":
    client.run(TOKEN)

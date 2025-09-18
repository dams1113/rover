# bot/discord_bot.py
import os
import discord
import subprocess
import datetime
import psutil
from modules.gps_reader import get_gps_data

# Lire le token depuis un fichier
with open("bot/token.txt") as f:
    TOKEN = f.read().strip()

# Intents obligatoires pour lire les messages
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    cmd = message.content.lower().strip()

    # ---- STATUS ----
    if cmd == "status":
        gps = get_gps_data()
        if gps["fix"]:
            gps_str = (f"{gps['latitude']}, {gps['longitude']} alt. {gps['altitude']}m "
                       f"- {gps['satellites']} sats\n🕒 Fix : {gps['timestamp']}")
        else:
            gps_str = "❌ Pas de fix GPS"

        # uptime
        uptime = datetime.timedelta(seconds=int(psutil.boot_time()))

        # Température CPU
        cpu_temp = 0.0
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                cpu_temp = int(f.read()) / 1000.0
        except:
            pass

        msg = (
            "🤖 **État du Rover**\n"
            f"🕒 Uptime : {uptime}\n"
            f"🌡 Température CPU : {cpu_temp:.1f}°C\n"
            f"📍 GPS : {gps_str}"
        )
        await message.channel.send(msg)

    # ---- MAP ----
    elif cmd == "map":
        await message.channel.send("🛰️ Génération de la carte...")
        try:
            subprocess.run([
                "python3", "tools/multi_map.py",
                "--out", "map/multi_map.html",
                "--basemap", "positron",
                "--heatmap", "--points",
                "--in", f"logs/gps_{datetime.date.today()}.csv"
            ], check=True)
            await message.channel.send("✅ Carte générée dans `map/multi_map.html`")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"⚠️ Erreur génération carte : {e}")

if __name__ == "__main__":
    client.run(TOKEN)

import os
import discord
import subprocess
import datetime
import psutil

from modules.gps_reader import get_gps_data

# ------------------------
# Chargement du TOKEN
# ------------------------
with open("bot/token.txt") as f:
    TOKEN = f.read().strip()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# ------------------------
# EVENTS
# ------------------------
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
                       f"- {gps['satellites']} sats\n"
                       f"🕒 Fix : {gps['timestamp']}")
        else:
            gps_str = "❌ Pas de fix GPS"

        # Uptime système
        uptime = datetime.timedelta(seconds=int(datetime.datetime.now().timestamp() - psutil.boot_time()))

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
            f"📍 GPS : {gps_str}\n"
        )
        await message.channel.send(msg)

    # ---- MAP ----
    elif cmd == "map":
        await message.channel.send("🛰️ Génération de la carte...")
        map_path = "map/multi_map.html"
        try:
            result = subprocess.run([
                "/home/rover/rover/.venv/bin/python", "tools/multi_map.py",
                "--out", map_path,
                "--basemap", "positron",
                "--heatmap", "--points",
                "--in", f"logs/gps_{datetime.date.today()}.csv"
            ], capture_output=True, text=True)

            if result.returncode == 0:
                await message.channel.send(file=discord.File(map_path))
            else:
                await message.channel.send(
                    f"⚠️ Erreur génération carte :\n```\n{result.stdout}\n{result.stderr}\n```"
                )
        except Exception as e:
            await message.channel.send(f"❌ Exception MAP : {e}")

    # ---- UPDATE ----
    elif cmd == "update":
        await message.channel.send("📡 Mise à jour en cours...")
        try:
            result = subprocess.run(["bash", "git_update.sh"], capture_output=True, text=True)
            if result.returncode == 0:
                await message.channel.send("✅ Mise à jour terminée, reboot nécessaire.")
            else:
                await message.channel.send(f"⚠️ Erreur update : {result.stderr}")
        except Exception as e:
            await message.channel.send(f"❌ Exception update : {e}")

    # ---- REBOOT ----
    elif cmd == "reboot":
        await message.channel.send("🔄 Reboot du Rover...")
        os.system("sudo reboot")


# ------------------------
# RUN
# ------------------------
if __name__ == "__main__":
    client.run(TOKEN)

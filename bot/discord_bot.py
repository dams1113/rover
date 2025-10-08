import os
import discord
import subprocess
import datetime
import psutil
import time
import asyncio

# --- Modules internes ---
from modules.gps_reader import get_gps_data
from modules import navigation
from modules import arduino_link

# --- Token Discord ---
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()

# --- Intents Discord ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Variables globales ---
last_telemetry = None   # 🆕 On garde la dernière ligne série reçue

# --- Chemin Python (venv) ---
PYTHON_BIN = "/home/rover/rover/.venv/bin/python"

# -------- EVENTS ----------
@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")

    # --- Canal Discord pour la télémétrie ---
    target_channel_name = "rover-server"
    for ch in client.get_all_channels():
        if ch.name == target_channel_name:
            arduino_link.discord_channel = ch
            print(f"[Arduino] Télémétrie connectée au canal : {ch.name}")
            break

    # --- Lancer la boucle de lecture série ---
    asyncio.get_event_loop().create_task(telemetry_loop())


# -------- LECTURE ARDUINO / TÉLÉMÉTRIE --------
async def telemetry_loop():
    """Lit en continu la télémétrie Arduino et l’envoie dans Discord."""
    global last_telemetry
    await client.wait_until_ready()
    channel = None

    while not client.is_closed():
        if not channel:
            channel = arduino_link.discord_channel

        line = arduino_link.read_line()
        if line:
            last_telemetry = line  # 🆕 On garde la dernière ligne reçue
        if line and channel:
            try:
                parts = {p.split(":")[0]: p.split(":")[1] for p in line.split(";") if ":" in p}
                bat = parts.get("BAT", "?")
                dist = parts.get("DIST", "?")
                ir_l = parts.get("IR_L", "?")
                ir_r = parts.get("IR_R", "?")

                dist_val = float(dist.replace("cm", "")) if "cm" in dist else -1
                if dist_val >= 0:
                    if dist_val < 10:
                        dist_emoji = "🟥"
                    elif dist_val < 20:
                        dist_emoji = "🟧"
                    else:
                        dist_emoji = "🟩"
                else:
                    dist_emoji = "⬜"

                msg = (
                    f"📡 **Télémétrie Arduino**\n"
                    f"🔋 Batterie moteur : `{bat}`\n"
                    f"📏 Distance : `{dist}` {dist_emoji}\n"
                    f"👁️ IR Gauche : `{ir_l}` | Droite : `{ir_r}`"
                )
                await channel.send(msg)
            except Exception as e:
                print(f"[Arduino] ⚠️ Erreur parsing télémétrie : {e} - {line}")

        await asyncio.sleep(2)


# -------- COMMANDES DISCORD --------
@client.event
async def on_message(message):
    global last_telemetry

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

        # 🆕 Extraction tension moteur depuis la dernière télémétrie
        bat_val = "Inconnue"
        if last_telemetry and "BAT:" in last_telemetry:
            try:
                bat_val = last_telemetry.split("BAT:")[1].split(";")[0]
            except Exception:
                pass

        msg = (
            "🤖 **État du Rover**\n"
            f"🕒 Uptime : {uptime}\n"
            f"🌡 Température CPU : {cpu_temp:.1f}°C\n"
            f"🔋 Tension batterie moteur : {bat_val}\n"
            f"📍 GPS : {gps_str}\n"
        )
        await message.channel.send(msg)

    # (le reste de tes commandes ne change pas)
    # FORWARD, BACKWARD, LEFT, RIGHT, STOP, GOTO, etc...


# -------- Lancement direct --------
def run_discord_bot():
    client.run(TOKEN)


if __name__ == "__main__":
    run_discord_bot()

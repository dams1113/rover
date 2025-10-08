import os
import re
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
last_telemetry = None   # garde la dernière ligne série reçue

# --- Chemin Python (venv) ---
PYTHON_BIN = "/home/rover/rover/.venv/bin/python"

# -------- EVENTS ----------
@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")

    # --- Canal Discord pour la télémétrie ---
    target_channel_name = "rover-server"  # ⚠️ ton salon Discord exact
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
            # Nettoie les caractères parasites et garde la dernière ligne
            clean_line = line.encode('ascii', 'ignore').decode().strip()
            last_telemetry = clean_line

        if line and channel:
            try:
                parts = {p.split(":")[0]: p.split(":")[1] for p in clean_line.split(";") if ":" in p}
                bat = parts.get("BAT", "?")
                dist = parts.get("DIST", "?")
                ir_l = parts.get("IR_L", "?")
                ir_r = parts.get("IR_R", "?")

                # Couleur distance
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

    # ---- HELP ----
    if cmd == "HELP":
        help_text = (
            "🤖 **Commandes disponibles**\n"
            "`STATUS` → État complet du Rover (CPU, GPS, Batterie...)\n"
            "`MAP` → Génère la carte GPS du jour\n"
            "`UPDATE` → Met à jour le code\n"
            "`REBOOT` → Redémarre le Raspberry Pi\n"
            "`FORWARD`, `BACKWARD`, `LEFT`, `RIGHT`, `STOP`\n"
            "`GOTO lat lon` → Navigation GPS\n"
        )
        await message.channel.send(help_text)
        return

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

        # --- Extraction robuste de la batterie
        bat_val = "Inconnue"
        if last_telemetry:
            try:
                clean_line = last_telemetry.encode('ascii', 'ignore').decode().strip()
                match_pct = re.search(r"BAT[:=]\s*(\d{1,3})\s*%", clean_line)
                match_v = re.search(r"BAT[:=]\s*(\d{1,2}\.\d{1,2})\s*V", clean_line)
                if match_pct:
                    bat_val = f"{match_pct.group(1)}%"
                elif match_v:
                    bat_val = f"{match_v.group(1)}V"
            except Exception as e:
                print(f"[STATUS] ⚠️ Erreur extraction batterie : {e}")

        msg = (
            "🤖 **État du Rover**\n"
            f"🕒 Uptime : {uptime}\n"
            f"🌡 Température CPU : {cpu_temp:.1f}°C\n"
            f"🔋 Batterie moteur : {bat_val}\n"
            f"📍 GPS : {gps_str}\n"
        )
        await message.channel.send(msg)
        return

    # ---- MAP ----
    if cmd == "MAP":
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
        return

    # ---- UPDATE ----
    if cmd == "UPDATE":
        await message.channel.send("📡 Mise à jour en cours...")
        try:
            subprocess.run(["bash", "git_update.sh"], check=True)
            await message.channel.send("✅ Mise à jour terminée. Utilise `REBOOT` si nécessaire.")
        except subprocess.CalledProcessError as e:
            await message.channel.send(f"⚠️ Erreur update : {e}")
        return

    # ---- REBOOT ----
    if cmd == "REBOOT":
        await message.channel.send("🔄 Reboot du Rover...")
        os.system("sudo reboot")
        return

    # ---- COMMANDES MOTEURS ----
    if cmd == "FORWARD":
        arduino_link.send_cmd("F")
        await message.channel.send("🚙 Avance")
        return

    if cmd == "BACKWARD":
        arduino_link.send_cmd("B")
        await message.channel.send("↩️ Recule")
        return

    if cmd == "LEFT":
        arduino_link.send_cmd("L")
        await message.channel.send("↪️ Gauche")
        return

    if cmd == "RIGHT":
        arduino_link.send_cmd("R")
        await message.channel.send("↩️ Droite")
        return

    if cmd == "STOP":
        arduino_link.send_cmd("S")
        await message.channel.send("🛑 Stop")
        return

    # ---- NAVIGATION GPS ----
    if cmd == "GOTO" and len(parts) >= 3:
        try:
            lat = float(parts[1])
            lon = float(parts[2])
            await message.channel.send(f"🧭 Navigation vers {lat}, {lon}")
            success = navigation.goto(lat, lon)
            await message.channel.send("✅ Objectif atteint !" if success else "⚠️ Navigation interrompue")
        except ValueError:
            await message.channel.send("❌ Format invalide. Exemple: `GOTO 42.1234 2.5678`")
        return


# -------- Lancement direct --------
def run_discord_bot():
    client.run(TOKEN)


if __name__ == "__main__":
    run_discord_bot()

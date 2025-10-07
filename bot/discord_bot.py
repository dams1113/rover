import os
import discord
import subprocess
import datetime
import psutil
import time
import asyncio

# --- Modules internes ---
from modules.gps_reader import get_gps_data
from modules import motors
from modules import autonomy
from modules import navigation
from modules import arduino_link

# --- Token Discord ---
TOKEN = os.getenv("DISCORD_TOKEN") or open("bot/token.txt").read().strip()

# --- Intents Discord ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Chemin Python (venv) ---
PYTHON_BIN = "/home/rover/rover/.venv/bin/python"


# -------- Utils ----------
def _parse_args(parts, default_sec=2.0, default_speed=50):
    """Analyse les arguments de commande (durée + vitesse)."""
    sec = default_sec
    spd = default_speed
    if len(parts) >= 2:
        try:
            sec = float(parts[1])
        except ValueError:
            pass
    if len(parts) >= 3:
        try:
            spd = int(parts[2])
        except ValueError:
            pass
    return sec, spd


# -------- Events ----------
@client.event
async def on_ready():
    print(f"[ROVER] ✅ Connecté en tant que {client.user}")

    # 🔗 Canal de télémétrie automatique
    target_channel_name = "rover-server"  # <-- Remplace par ton salon Discord exact
    for ch in client.get_all_channels():
        if ch.name == target_channel_name:
            arduino_link.discord_channel = ch
            print(f"[Arduino] Télémétrie connectée au canal : {ch.name}")
            break

    # Démarre la boucle de lecture série Arduino
    asyncio.get_event_loop().create_task(telemetry_loop())


async def telemetry_loop():
    """Boucle d'écoute des messages Arduino et publication Discord."""
    await client.wait_until_ready()
    channel = arduino_link.discord_channel
    while not client.is_closed():
        line = arduino_link.read_line()
        if line and channel:
            try:
                # Exemple de ligne : "BAT:87%;DIST:32.5cm;IR_L:1;IR_R:0"
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
                    f"🔋 Batterie : `{bat}`\n"
                    f"📏 Distance : `{dist}` {dist_emoji}\n"
                    f"👁️ IR Gauche : `{ir_l}` | Droite : `{ir_r}`"
                )
                await channel.send(msg)
            except Exception as e:
                print(f"[Arduino] ⚠️ Erreur format : {e} - {line}")
        await asyncio.sleep(2)


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

    # ---- MOUVEMENTS ----
    elif cmd == "FORWARD":
        sec, spd = _parse_args(parts, 2.0, 55)
        motors.forward(speed=spd, duration=sec)
        arduino_link.send_cmd("F")
        await message.channel.send(f"🚙 Avance {sec}s @ {spd}%")

    elif cmd == "BACKWARD":
        sec, spd = _parse_args(parts, 2.0, 50)
        motors.backward(speed=spd, duration=sec)
        arduino_link.send_cmd("B")
        await message.channel.send(f"↩️ Recule {sec}s @ {spd}%")

    elif cmd == "LEFT":
        sec, spd = _parse_args(parts, 1.0, 55)
        motors.turn_left(speed=spd, duration=sec)
        arduino_link.send_cmd("L")
        await message.channel.send(f"↪️ Gauche {sec}s @ {spd}%")

    elif cmd == "RIGHT":
        sec, spd = _parse_args(parts, 1.0, 55)
        motors.turn_right(speed=spd, duration=sec)
        arduino_link.send_cmd("R")
        await message.channel.send(f"↩️ Droite {sec}s @ {spd}%")

    elif cmd == "STOP":
        motors.stop()
        arduino_link.send_cmd("S")
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

    # ---- NAVIGATION ----
    elif cmd == "GOTO":
        if len(parts) >= 3:
            try:
                lat = float(parts[1])
                lon = float(parts[2])
                await message.channel.send(f"🧭 Navigation vers {lat}, {lon}")
                success = navigation.goto(lat, lon)
                await message.channel.send("✅ Objectif atteint !" if success else "⚠️ Navigation interrompue")
            except ValueError:
                await message.channel.send("❌ Format invalide. Exemple: `GOTO 42.1234 2.5678`")
        else:
            await message.channel.send("❌ Utilisation: `GOTO lat lon`")


# -------- Run ----------
def run_discord_bot():
    client.run(TOKEN)

import discord
import asyncio
import socket
import psutil
import time

from modules import gps, energie, moteurs, radio

# Charger le token
with open("bot/token.txt", "r") as f:
    TOKEN = f.read().strip()

CHANNEL_ID = 1398325400475537462

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Température CPU
def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_str = f.read().strip()
            return round(int(temp_str) / 1000.0, 1)
    except:
        return "N/A"

# Adresse IP réelle
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "N/A"

# Génère le message complet d’état du rover
def get_etat_rover():
    energie_data = energie.get_battery_status()
    gps_data = gps.get_gps_data()

    ip = get_ip()
    cpu = psutil.cpu_percent()
    temp = get_cpu_temp()
    uptime = time.strftime("%Hh%Mm", time.gmtime(time.time() - psutil.boot_time()))

    if isinstance(gps_data, dict) and "latitude" in gps_data:
        gps_msg = (
            f"📍 Latitude : {gps_data['latitude']}°\n"
            f"📍 Longitude : {gps_data['longitude']}°\n"
            f"📏 Altitude : {gps_data['altitude']} m\n"
            f"📡 Satellites : {gps_data['satellites']} | Fix : {gps_data['fix']}"
        )
    elif "error" in gps_data:
        gps_msg = f"❌ GPS : {gps_data['error']}"
    else:
        gps_msg = "❌ GPS : données non valides"

    message = (
        f"📡 **État du Rover**\n"
        f"🔋 Tension : {energie_data['voltage']} V | Courant : {energie_data['current']} A\n"
        f"{gps_msg}\n"
        f"🧠 CPU : {cpu}% | 🌡️ Temp : {temp}°C\n"
        f"🕐 Uptime : {uptime} | 🌐 IP : {ip}"
    )
    return message

@client.event
async def on_ready():
    print(f"[BOT] Connecté en tant que {client.user}")
    if not hasattr(client, 'etat_task'):
        client.etat_task = client.loop.create_task(envoyer_etat_recurrent())

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    cmd = message.content.strip().upper()

    if cmd == "STATUS":
        msg = get_etat_rover()
        await message.channel.send(msg)
    elif cmd == "AVANCE":
        moteurs.avance()
        await message.channel.send("🚗 Avance")
    elif cmd == "RECULE":
        moteurs.recule()
        await message.channel.send("🔙 Recule")
    elif cmd == "STOP":
        moteurs.stop()
        await message.channel.send("⛔ Stop")
    elif cmd == "GPS":
        gps_info = get_etat_rover().split('\n')[2:6]
        await message.channel.send("📍 GPS :\n" + '\n'.join(gps_info))
    elif cmd == "ENERGIE":
        data = energie.get_battery_status()
        await message.channel.send(f"🔋 Tension : {data['voltage']} V | Courant : {data['current']} A")
    elif cmd == "RADIO":
        msg = radio.ecouter_radio()
        await message.channel.send(f"📡 Radio : {msg}")

async def envoyer_etat_recurrent():
    await client.wait_until_ready()
    canal = client.get_channel(CHANNEL_ID)

    while not client.is_closed():
        try:
            message = get_etat_rover()
            await canal.send(message)
        except Exception as e:
            print(f"[ERREUR envoi état] {e}")

        await asyncio.sleep(3 * 3600)  # ⏱️ toutes les 3h

def run():
    client.run(TOKEN)

import threading
import asyncio

from bot import discord_bot
from modules.gps_reader import start_gps_loop
from modules.gps_logger import log_loop

def main():
    # Démarrer la boucle GPS
    start_gps_loop()
    print("[MAIN] Boucle GPS démarrée")

    # Démarrer le logger GPS
    threading.Thread(target=log_loop, args=(30,), daemon=True).start()
    print("[MAIN] GPS Logger lancé (intervalle = 30s)")

    # Démarrer le bot Discord
    asyncio.run(discord_bot.client.start(discord_bot.TOKEN))

if __name__ == "__main__":
    main()


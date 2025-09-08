import threading
import asyncio

from bot import discord_bot
from modules.gps_logger import log_loop
from modules.gps_reader import start_gps_loop


def start_gps_logger():
    """Démarre le logger GPS dans un thread"""
    t = threading.Thread(target=log_loop, args=(30,), daemon=True)
    t.start()
    print("[MAIN] GPS Logger lancé (intervalle = 30s)")


def main():
    # Lancer la boucle GPS (lecture série)
    start_gps_loop()
    print("[MAIN] Boucle GPS démarrée")

    # Lancer le logger GPS
    start_gps_logger()

    # Lancer le bot Discord
    asyncio.run(discord_bot.client.start(discord_bot.TOKEN))


if __name__ == "__main__":
    main()

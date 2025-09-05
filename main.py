import threading
import asyncio

from bot import discord_bot
from modules.gps_logger import log_loop


def start_gps_logger():
    """Démarre le logger GPS dans un thread"""
    t = threading.Thread(target=log_loop, args=(30,), daemon=True)
    t.start()
    print("[MAIN] GPS Logger lancé (intervalle = 30s)")


def main():
    # Lancer le logger GPS
    start_gps_logger()

    # Lancer le bot Discord
    asyncio.run(discord_bot.client.start(discord_bot.TOKEN))


if __name__ == "__main__":
    main()

import threading
import asyncio

from bot import discord_bot
from modules.gps_reader import start_gps_loop
from modules.gps_logger import log_loop


def start_gps_logger():
    """Démarre le logger GPS dans un thread"""
    t = threading.Thread(target=log_loop, args=(30,), daemon=True)  # 30 secondes par défaut
    t.start()
    print("[MAIN] GPS Logger lancé (intervalle = 30s)")


def main():
    # Lancer la boucle GPS (lecture série en continu)
    start_gps_loop()
    print("[MAIN] Boucle GPS démarrée")

    # Lancer le logger GPS (écriture CSV)
    start_gps_logger()

    # Lancer le bot Discord
    asyncio.run(discord_bot.client.start(discord_bot.TOKEN))


if __name__ == "__main__":
    main()

from bot import discord_bot
import threading
from modules.gps_logger import log_loop

# Démarre l’enregistrement GPS toutes les 30 s
threading.Thread(target=log_loop, args=(30,), daemon=True).start()


if __name__ == "__main__":
    import asyncio
    asyncio.run(discord_bot.client.start(discord_bot.TOKEN))

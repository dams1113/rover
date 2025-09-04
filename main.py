from bot import discord_bot
import threading
from modules.gps_logger import log_loop
threading.Thread(target=log_loop, daemon=True).start()

if __name__ == "__main__":
    import asyncio
    asyncio.run(discord_bot.client.start(discord_bot.TOKEN))

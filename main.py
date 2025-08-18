from bot import discord_bot

if __name__ == "__main__":
    import asyncio
    asyncio.run(discord_bot.client.start(discord_bot.TOKEN))

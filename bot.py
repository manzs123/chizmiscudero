import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="c!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user} (ID: {bot.user.id})")


async def main():
    async with bot:
        await bot.load_extension("cogs.recording")
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())

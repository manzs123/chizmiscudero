import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True  # required for prefix commands

bot = commands.Bot(command_prefix="c!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user} (ID: {bot.user.id})")


bot.load_extension("cogs.recording")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))

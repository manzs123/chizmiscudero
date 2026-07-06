import os
import asyncio
import ctypes
import ctypes.util
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


def _load_opus():
    if discord.opus.is_loaded():
        print("[Opus] Already loaded by py-cord")
        return
    candidates = [
        "libopus.so.0",
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        "/usr/lib/aarch64-linux-gnu/libopus.so.0",
        "libopus.so",
        "opus",
    ]
    for lib in candidates:
        try:
            discord.opus.load_opus(lib)
            print(f"[Opus] Loaded: {lib}")
            return
        except OSError:
            pass
    found = ctypes.util.find_library("opus")
    if found:
        try:
            discord.opus.load_opus(found)
            print(f"[Opus] Loaded via find_library: {found}")
            return
        except OSError:
            pass
    print("[Opus] WARNING: Could not load opus — voice will not work")


_load_opus()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="c!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user} (ID: {bot.user.id})")
    print(f"[Opus] Loaded: {discord.opus.is_loaded()}")


async def main():
    async with bot:
        bot.load_extension("cogs.recording")
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())

import os
import asyncio
import discord
from discord.ext import commands
from services.gemini import transcribe_audio, summarize_transcript

SUMMARY_CHANNEL_ID = int(os.getenv("SUMMARY_CHANNEL_ID", 0))
_EMBED_FIELD_LIMIT = 1024


class RecordingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.connections: dict[int, discord.VoiceClient] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        # Clean up if the bot itself gets unexpectedly disconnected from VC
        if member.id != self.bot.user.id:
            return
        if before.channel is not None and after.channel is None:
            self.connections.pop(before.channel.guild.id, None)

    @commands.group(name="chismisan", invoke_without_command=True)
    async def chismisan(self, ctx: commands.Context):
        await ctx.send("Use `c!chismisan na` to start recording a meeting.")

    @chismisan.command(name="na")
    async def chismisan_na(self, ctx: commands.Context):
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel first.")

        if ctx.guild.id in self.connections:
            return await ctx.send(
                "A recording is already in progress. Use `c!kansela` to reset it."
            )

        # Kick out any leftover voice client from a broken previous session
        if ctx.guild.voice_client:
            try:
                await ctx.guild.voice_client.disconnect(force=True)
            except Exception:
                pass

        await ctx.send(f"[1/4] Opus loaded: `{discord.opus.is_loaded()}`")

        if ctx.guild.voice_client:
            try:
                await ctx.guild.voice_client.disconnect(force=True)
                await ctx.send("[2/4] Cleared stale voice client.")
            except Exception as e:
                await ctx.send(f"[2/4] Stale disconnect warning: `{e}`")
        else:
            await ctx.send("[2/4] No stale voice client.")

        try:
            channel = ctx.author.voice.channel
            await ctx.send(f"[3/4] Connecting to **{channel.name}**...")
            vc = await channel.connect(timeout=60.0, reconnect=True)

            # Wait up to 15 s for the voice connection to fully establish
            for _ in range(75):
                if vc.is_connected():
                    break
                await asyncio.sleep(0.2)

            await ctx.send(f"[3/4] is_connected=`{vc.is_connected()}`")

            if not vc.is_connected():
                await vc.disconnect(force=True)
                await ctx.send("Voice connection failed after 15 s. This is likely a network/UDP issue with Railway.")
                return

            self.connections[ctx.guild.id] = vc

            await ctx.send("[4/4] Starting recording...")
            vc.start_recording(discord.sinks.WaveSink(), self._on_recording_done, ctx)
            await ctx.send("Recording started! Use `c!stap na` when the meeting is over.")
        except Exception as exc:
            self.connections.pop(ctx.guild.id, None)
            try:
                await ctx.guild.voice_client.disconnect(force=True)
            except Exception:
                pass
            await ctx.send(f"Failed: `{type(exc).__name__}: {exc}`")

    @commands.command(name="kansela")
    async def kansela(self, ctx: commands.Context):
        vc = self.connections.pop(ctx.guild.id, None)
        if vc is None:
            return await ctx.send("No active recording to cancel.")
        try:
            vc.stop_recording()
        except Exception:
            pass
        try:
            await vc.disconnect()
        except Exception:
            pass
        await ctx.send("Recording cancelled and bot disconnected.")

    @commands.group(name="stap", invoke_without_command=True)
    async def stap(self, ctx: commands.Context):
        await ctx.send("Use `c!stap na` to stop recording and generate a summary.")

    @stap.command(name="na")
    async def stap_na(self, ctx: commands.Context):
        if ctx.guild.id not in self.connections:
            return await ctx.send("No active recording in this server.")

        vc = self.connections.pop(ctx.guild.id)
        vc.stop_recording()  # finishes recording and schedules _on_recording_done
        try:
            await vc.disconnect()
        except Exception:
            pass
        await ctx.send("Stopped! Generating summary — check the summary channel shortly.")

    async def _on_recording_done(
        self,
        sink: discord.sinks.WaveSink,
        ctx: commands.Context,
    ):
        summary_channel = self.bot.get_channel(SUMMARY_CHANNEL_ID)
        if not summary_channel:
            print(f"[Bot] SUMMARY_CHANNEL_ID {SUMMARY_CHANNEL_ID} not found.")
            return

        try:
            if not sink.audio_data:
                await summary_channel.send("Recording ended but no audio was captured.")
                return

            participants: list[str] = []
            audio_map: dict[str, bytes] = {}

            for user_id, audio_data in sink.audio_data.items():
                member = ctx.guild.get_member(user_id)
                name = member.display_name if member else str(user_id)
                participants.append(name)
                audio_data.file.seek(0)
                audio_map[name] = audio_data.file.read()

            status = await summary_channel.send(
                f"Processing meeting recording with **{len(participants)}** participant(s)..."
            )

            lines: list[str] = []
            for name, audio_bytes in audio_map.items():
                text = await transcribe_audio(audio_bytes, name)
                if text:
                    lines.append(f"**{name}**: {text}")

            if not lines:
                await status.edit(content="No speech was detected in the recording.")
                return

            full_transcript = "\n".join(lines)
            summary = await summarize_transcript(full_transcript, participants)

            embed = discord.Embed(title="Meeting Summary", color=discord.Color.blurple())
            embed.add_field(
                name="Participants",
                value=", ".join(participants),
                inline=False,
            )

            chunks = [
                summary[i : i + _EMBED_FIELD_LIMIT]
                for i in range(0, len(summary), _EMBED_FIELD_LIMIT)
            ]
            for i, chunk in enumerate(chunks):
                embed.add_field(
                    name="Summary" if i == 0 else "​",
                    value=chunk,
                    inline=False,
                )

            await status.delete()
            await summary_channel.send(embed=embed)

        except Exception as exc:
            print(f"[Bot] Error in _on_recording_done: {exc}")
            await summary_channel.send(f"Something went wrong while generating the summary: `{exc}`")


def setup(bot: commands.Bot):
    bot.add_cog(RecordingCog(bot))

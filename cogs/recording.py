import os
import discord
from discord.ext import commands
from services.gemini import transcribe_audio, summarize_transcript

SUMMARY_CHANNEL_ID = int(os.getenv("SUMMARY_CHANNEL_ID", 0))

_EMBED_FIELD_LIMIT = 1024


class RecordingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.connections: dict[int, discord.VoiceClient] = {}

    @commands.group(name="chismisan", invoke_without_command=True)
    async def chismisan(self, ctx: commands.Context):
        await ctx.send("Use `c!chismisan na` to start recording a meeting.")

    @chismisan.command(name="na")
    async def chismisan_na(self, ctx: commands.Context):
        if not ctx.author.voice:
            return await ctx.send("You need to be in a voice channel first.")

        if ctx.guild.id in self.connections:
            return await ctx.send("A recording is already in progress in this server.")

        channel = ctx.author.voice.channel
        vc = await channel.connect()
        self.connections[ctx.guild.id] = vc

        vc.start_recording(
            discord.sinks.WaveSink(),
            self._on_recording_done,
            ctx,
        )

        await ctx.send(
            f"Recording started in **{channel.name}**. Use `c!stap na` when the meeting is over."
        )

    @commands.group(name="stap", invoke_without_command=True)
    async def stap(self, ctx: commands.Context):
        await ctx.send("Use `c!stap na` to stop recording and generate a summary.")

    @stap.command(name="na")
    async def stap_na(self, ctx: commands.Context):
        if ctx.guild.id not in self.connections:
            return await ctx.send("No active recording in this server.")

        vc = self.connections.pop(ctx.guild.id)
        vc.stop_recording()  # triggers _on_recording_done
        await ctx.send("Recording stopped. Generating summary — check the summary channel shortly.")

    async def _on_recording_done(
        self,
        sink: discord.sinks.WaveSink,
        ctx: commands.Context,
    ):
        await sink.vc.disconnect()

        summary_channel = self.bot.get_channel(SUMMARY_CHANNEL_ID)
        if not summary_channel:
            print(f"[RecordingCog] SUMMARY_CHANNEL_ID {SUMMARY_CHANNEL_ID} not found.")
            return

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


def setup(bot: commands.Bot):
    bot.add_cog(RecordingCog(bot))

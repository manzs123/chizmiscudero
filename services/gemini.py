import os
import asyncio
import tempfile
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_model = genai.GenerativeModel("gemini-1.5-flash")

_MIN_AUDIO_BYTES = 1000  # skip near-empty recordings


async def transcribe_audio(audio_bytes: bytes, username: str) -> str:
    return await asyncio.get_event_loop().run_in_executor(
        None, _transcribe, audio_bytes, username
    )


def _transcribe(audio_bytes: bytes, username: str) -> str:
    if len(audio_bytes) < _MIN_AUDIO_BYTES:
        return ""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        uploaded = genai.upload_file(tmp_path, mime_type="audio/wav")
        response = _model.generate_content([
            uploaded,
            (
                f"Transcribe the speech in this audio. The speaker is '{username}' in a team meeting. "
                "Output only the spoken words exactly as said. "
                "If there is only silence or background noise, respond with exactly: [no speech]"
            ),
        ])
        text = response.text.strip()
        return "" if text == "[no speech]" else text
    except Exception as exc:
        print(f"[Gemini] Transcription error for {username}: {exc}")
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def summarize_transcript(transcript: str, participants: list[str]) -> str:
    return await asyncio.get_event_loop().run_in_executor(
        None, _summarize, transcript, participants
    )


def _summarize(transcript: str, participants: list[str]) -> str:
    try:
        prompt = f"""You are a professional meeting summarizer. Below is a transcript from a voice meeting.

Participants: {", ".join(participants)}

Transcript:
{transcript}

Write a concise, structured summary covering:
1. **Key Topics** — main subjects discussed
2. **Decisions Made** — any conclusions or agreements reached
3. **Action Items** — tasks assigned or committed to (with owner if mentioned)
4. **Notable Highlights** — any important points per participant

Be brief, professional, and factual. If a section has nothing relevant, omit it."""

        response = _model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        print(f"[Gemini] Summarization error: {exc}")
        return "Summary generation failed."

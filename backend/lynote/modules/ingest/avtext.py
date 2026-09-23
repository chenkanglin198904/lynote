"""Audio/video to locatable transcript. Must not invent unheard words."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from lynote.llm.client import LlmError, complete_audio_transcript, complete_vision_text, is_configured

TranscribeFn = Callable[[bytes, str], str]
VisionFn = Callable[[list[bytes]], str]


def transcribe_audio(data: bytes, filename: str = "audio.webm", *, transcribe: TranscribeFn | None = None) -> str:
    if not data:
        raise ValueError("空音频无法入库")
    fn = transcribe or _default_transcribe
    text = (fn(data, filename) or "").strip()
    if not text:
        raise ValueError("这段音频转写不出文字（需要配置 LLM_API_KEY，且不能发明未听到的句子）")
    return text


def transcribe_video(
    data: bytes,
    filename: str = "video.mp4",
    *,
    transcribe: TranscribeFn | None = None,
    vision: VisionFn | None = None,
) -> str:
    if not data:
        raise ValueError("空视频无法入库")
    audio_blob, frames = _split_video(data, filename)
    parts: list[str] = []
    if frames:
        ocr = (vision or _default_vision)(frames).strip()
        if ocr:
            parts.append("【画面文字】\n" + ocr)
    if audio_blob:
        spoken = transcribe_audio(audio_blob, "track.wav", transcribe=transcribe)
        parts.append("【旁白】\n" + spoken)
    elif not parts:
        spoken = transcribe_audio(data, filename, transcribe=transcribe)
        parts.append("【旁白】\n" + spoken)
    text = "\n\n".join(parts).strip()
    if not text:
        raise ValueError("这段视频抽不出旁白或画面文字，不会发明未见内容")
    return text


def _default_transcribe(data: bytes, filename: str) -> str:
    if not is_configured():
        raise ValueError("音频/视频转写需要配置 LLM_API_KEY")
    try:
        return complete_audio_transcript(data, filename)
    except LlmError as exc:
        raise ValueError(str(exc)) from exc


def _default_vision(images: list[bytes]) -> str:
    if not images:
        return ""
    if not is_configured():
        return ""
    try:
        return complete_vision_text(images)
    except LlmError:
        return ""


def _split_video(data: bytes, filename: str) -> tuple[bytes | None, list[bytes]]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None, []
    suffix = Path(filename).suffix or ".mp4"
    with tempfile.TemporaryDirectory() as raw_dir:
        folder = Path(raw_dir)
        src = folder / f"in{suffix}"
        wav = folder / "out.wav"
        src.write_bytes(data)
        audio: bytes | None = None
        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
                check=True,
                capture_output=True,
                timeout=120,
            )
            if wav.exists():
                audio = wav.read_bytes()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            audio = None
        frames: list[bytes] = []
        pattern = folder / "frame-%02d.jpg"
        try:
            subprocess.run(
                [ffmpeg, "-y", "-i", str(src), "-vf", "fps=1/20,scale=960:-2", "-frames:v", "6", str(pattern)],
                check=True,
                capture_output=True,
                timeout=120,
            )
            frames = [path.read_bytes() for path in sorted(folder.glob("frame-*.jpg")) if path.stat().st_size > 0]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            frames = []
        return audio, frames

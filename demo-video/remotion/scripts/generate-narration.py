"""Generate deterministic scene-level narration and subtitle sources.

The script uses Microsoft Edge neural TTS for the public, synthetic narration
text only. It never sends LocalGuard documents, credentials, or application
data. Generated media is written under ``public/audio`` for Remotion.
"""

from __future__ import annotations

import asyncio
import json
import re
import textwrap
from pathlib import Path

import edge_tts


ROOT = Path(__file__).resolve().parents[1]
SCENES_PATH = Path(__file__).with_name("narration-scenes.json")
AUDIO_DIRECTORY = ROOT / "public" / "audio"
CAPTION_DIRECTORY = ROOT / "public" / "captions"
DEMO_OUTPUT_DIRECTORY = ROOT.parent / "output"
VOICE = "en-US-AndrewMultilingualNeural"
RATE = "-12%"
PITCH = "-1Hz"


async def generate_scene(scene: dict[str, object]) -> None:
    scene_id = str(scene["id"])
    text = str(scene["text"])
    media_path = AUDIO_DIRECTORY / f"{scene_id}.mp3"
    subtitle_path = AUDIO_DIRECTORY / f"{scene_id}.srt"
    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate=RATE,
        pitch=PITCH,
    )
    submaker = edge_tts.SubMaker()
    with media_path.open("wb") as media_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                media_file.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                submaker.feed(chunk)
    subtitle_text = submaker.get_srt().replace("\r\n", "\n").rstrip() + "\n"
    subtitle_path.write_text(subtitle_text, encoding="utf-8")


async def main() -> None:
    scenes = json.loads(SCENES_PATH.read_text(encoding="utf-8"))
    AUDIO_DIRECTORY.mkdir(parents=True, exist_ok=True)
    CAPTION_DIRECTORY.mkdir(parents=True, exist_ok=True)
    DEMO_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for scene in scenes:
        await generate_scene(scene)
    combined_srt = combine_subtitles(scenes)
    (CAPTION_DIRECTORY / "product-demo.srt").write_text(combined_srt, encoding="utf-8")
    (DEMO_OUTPUT_DIRECTORY / "product-demo.srt").write_text(combined_srt, encoding="utf-8")
    manifest = {
        "schemaVersion": 1,
        "voice": VOICE,
        "rate": RATE,
        "pitch": PITCH,
        "privacyNote": "Only the public synthetic narration text was sent to Edge TTS.",
        "scenes": scenes,
    }
    (AUDIO_DIRECTORY / "narration-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def combine_subtitles(scenes: list[dict[str, object]]) -> str:
    cues: list[tuple[int, int, str]] = []
    timestamp_pattern = re.compile(
        r"(?P<start>\d{2}:\d{2}:\d{2},\d{3}) --> (?P<end>\d{2}:\d{2}:\d{2},\d{3})"
    )
    for scene in scenes:
        offset_ms = int(float(scene["start"]) * 1000)
        maximum_ms = int(float(scene["end"]) * 1000) - 100
        subtitle_path = AUDIO_DIRECTORY / f"{scene['id']}.srt"
        blocks = subtitle_path.read_text(encoding="utf-8").strip().split("\n\n")
        for block in blocks:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 3:
                continue
            match = timestamp_pattern.fullmatch(lines[1])
            if match is None:
                continue
            start_ms = offset_ms + parse_timestamp(match.group("start"))
            end_ms = min(offset_ms + parse_timestamp(match.group("end")), maximum_ms)
            if end_ms <= start_ms:
                continue
            text = " ".join(lines[2:])
            parts = textwrap.wrap(
                text,
                width=92,
                break_long_words=False,
                break_on_hyphens=False,
            ) or [text]
            if len(parts) > 1 and len(parts[-1]) < 24:
                parts[-2] = f"{parts[-2]} {parts[-1]}"
                parts.pop()
            duration_ms = end_ms - start_ms
            total_weight = sum(len(part) for part in parts)
            cursor_ms = start_ms
            for part_index, part in enumerate(parts):
                if part_index == len(parts) - 1:
                    part_end_ms = end_ms
                else:
                    part_end_ms = cursor_ms + round(duration_ms * len(part) / total_weight)
                cues.append((cursor_ms, part_end_ms, part))
                cursor_ms = part_end_ms
    rendered: list[str] = []
    for index, (start_ms, end_ms, text) in enumerate(cues, start=1):
        rendered.extend(
            [
                str(index),
                f"{format_timestamp(start_ms)} --> {format_timestamp(end_ms)}",
                text,
                "",
            ]
        )
    return "\n".join(rendered).rstrip() + "\n"


def parse_timestamp(value: str) -> int:
    hours, minutes, remainder = value.split(":")
    seconds, milliseconds = remainder.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1000
        + int(milliseconds)
    )


def format_timestamp(value: int) -> str:
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


if __name__ == "__main__":
    asyncio.run(main())

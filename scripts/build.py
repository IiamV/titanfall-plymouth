#!/usr/bin/env python3
"""Build Plymouth PNGs and a desktop preview using only Python and FFmpeg."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
THEME = BUILD / "themes" / "titanfall"
FPS = 24
START = 0.534  # Remove the measured black lead-in, preserve the cockpit sequence.


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def ffmpeg(*args):
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args)


def build(audio=False):
    for executable in ("ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            raise SystemExit(f"Missing dependency: {executable}")
    BUILD.mkdir(exist_ok=True)
    # Generate into a temporary sibling so a failed conversion preserves the last build.
    with tempfile.TemporaryDirectory(prefix="titanfall-", dir=BUILD) as temporary:
        stage = Path(temporary)
        ffmpeg("-ss", START, "-i", ROOT / "closing-pilot.mp4", "-an", "-vf",
               f"fps={FPS},scale=960:540", "-start_number", 0,
               stage / "frame-%d.png")
        count = len(list(stage.glob("frame-*.png")))
        if count < 2:
            raise SystemExit("Video produced fewer than two frames")
        shutil.copy2(ROOT / "marauder-logo.png", stage)
        for name, color in (("panel", "black"), ("progress", "0x93b9a5")):
            ffmpeg("-f", "lavfi", "-i", f"color=c={color}:s=16x16",
                   "-frames:v", 1, "-threads", 1, stage / f"{name}.png")
        script = (ROOT / "theme/titanfall.script").read_text().replace("@FRAME_COUNT@", str(count))
        (stage / "titanfall.script").write_text(script)
        shutil.copy2(ROOT / "theme/titanfall.plymouth", stage)
        THEME.parent.mkdir(exist_ok=True)
        if THEME.exists():
            shutil.rmtree(THEME)
        shutil.copytree(stage, THEME)
    duration = count / FPS
    # Desktop preview mirrors the clip, one-second emblem fade, and final hold.
    ffmpeg("-framerate", FPS, "-start_number", 0, "-i", THEME / "frame-%d.png",
           "-loop", 1, "-framerate", FPS, "-i", THEME / "marauder-logo.png",
           "-filter_complex",
           f"[1:v]scale=162:162,format=rgba,fade=t=in:st=0:d=1:alpha=1[logo];"
           f"color=black:s=960x540:r={FPS}:d=4[bg];"
           "[bg][logo]overlay=x=(W-w)/2:y=151:shortest=1,"
           "drawtext=text='PILOT LINK ESTABLISHED':fontcolor=0xbfd bcc:fontsize=21:"
           "x=(w-tw)/2:y=351:alpha='min(1,t)'[outro];"
           "[0:v]setsar=1[clip];[clip][outro]concat=n=2:v=1:a=0[out]".replace("0xbfd bcc", "0xbfdbcc"),
           "-map", "[out]", "-an", "-t", duration + 4,
           "-c:v", "libx264", "-crf", 20, "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", BUILD / "preview.mp4")
    if audio:
        ffmpeg("-i", BUILD / "preview.mp4", "-i", ROOT / "machine-noise.m4a",
               "-i", ROOT / "marauder-corps.m4a", "-i", ROOT / "the-line.m4a",
               "-filter_complex",
               f"[1:a]volume=0.6[a];[2:a]adelay={int(duration*1000)}:all=1[b];"
               f"[3:a]adelay={int((duration+2.212)*1000)}:all=1[c];"
               "[a][b][c]amix=inputs=3:normalize=0,alimiter=limit=0.9[mix]",
               "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac",
               "-t", duration + 4, "-movflags", "+faststart", BUILD / "preview-with-audio.mp4")
    manifest = {"frames": count, "fps": FPS, "clip_seconds": duration,
                "trim_start": START, "theme": str(THEME),
                "reference": "https://www.youtube.com/watch?v=Sn50EDiLVAk"}
    (BUILD / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Built {count} frames ({duration:.2f}s). Theme: {THEME}")
    print(f"Preview: {BUILD / 'preview.mp4'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", action="store_true", help="also mix supplied audio for desktop preview")
    build(parser.parse_args().audio)

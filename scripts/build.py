#!/usr/bin/env python3
"""Build black/white native Plymouth themes and matching desktop previews."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
FPS = 24
DURATION = 7


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def ffmpeg(*args):
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args)


def build(audio):
    for executable in ("ffmpeg", "magick"):
        if not shutil.which(executable):
            raise SystemExit(f"Missing dependency: {executable}")
    BUILD.mkdir(exist_ok=True)
    for variant, bg, fg in (("black", "black", "white"), ("white", "white", "black")):
        name = f"titanfall-{variant}"
        theme = BUILD / "themes" / name
        theme.mkdir(parents=True, exist_ok=True)
        # A shared angular seam converges from both sides, then dissolves.
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
<g fill="none" stroke="{fg}" stroke-width="3" stroke-linejoin="miter">
<path d="M-10 232 H170 L208 256 H370 L394 270 H566 L590 256 H752 L790 232 H970"/>
<path opacity=".35" stroke-width="1" d="M0 220 H174 L212 244 H360 M600 244 H748 L786 220 H960"/>
<path stroke-width="2" d="M40 214 V228 M52 214 V228 M908 214 V228 M920 214 V228"/>
</g></svg>'''
        svg_path = theme / "closing-lines.svg"
        svg_path.write_text(svg)
        run("magick", "-background", "none", svg_path, theme / "closing-lines.png")
        # The supplied .png is actually WebP; Plymouth needs a real PNG.
        run("magick", ROOT / "marauder-logo.png", "PNG32:" + str(theme / "marauder-logo.png"))
        for asset, color in (("panel", bg),):
            ffmpeg("-f", "lavfi", "-i", f"color=c={color}:s=16x16", "-frames:v", 1,
                   "-threads", 1, theme / f"{asset}.png")
        script = (ROOT / "theme/titanfall.script").read_text()
        script = script.replace("@BG@", "0" if bg == "black" else "1")
        script = script.replace("@FG@", "1" if fg == "white" else "0")
        (theme / f"{name}.script").write_text(script)
        descriptor = (ROOT / "theme/titanfall.plymouth").read_text()
        descriptor = descriptor.replace("titanfall", name).replace("Titanfall Pilot Link", f"Titanfall Pilot Link ({variant})")
        (theme / f"{name}.plymouth").write_text(descriptor)
        # Mirror the native 24Hz smoothstep motion in a portable video preview.
        u = "min(1,max(0,(t-0.6)/3))"
        offset = f"540*(1-({u})*({u})*(3-2*({u})))"
        filters = (
            "[1:v]format=rgba,fade=t=out:st=3.8:d=0.8:alpha=1,split=2[upper][lower];"
            f"[0:v][upper]overlay=x=0:y='-({offset})':eval=frame[a];"
            f"[a][lower]overlay=x=0:y='{offset}':eval=frame[b];"
            "[2:v]scale=151:151,format=rgba,fade=t=in:st=0.25:d=0.65:alpha=1,fade=t=out:st=3.8:d=0.8:alpha=1[logo];"
            "[b][logo]overlay=x=(W-w)/2:y=(H-h)/2:shortest=1[out]"
        )
        preview = BUILD / f"preview-{variant}.mp4"
        ffmpeg("-f", "lavfi", "-i", f"color=c={bg}:s=960x540:r={FPS}:d={DURATION}",
               "-loop", 1, "-framerate", FPS, "-i", theme / "closing-lines.png",
               "-loop", 1, "-framerate", FPS, "-i", theme / "marauder-logo.png",
               "-filter_complex", filters, "-map", "[out]", "-an", "-t", DURATION,
               "-c:v", "libx264", "-crf", 18, "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", preview)
        if audio:
            ffmpeg("-i", preview, "-i", ROOT / "machine-noise.m4a",
                   "-i", ROOT / "marauder-corps.m4a", "-i", ROOT / "the-line.m4a",
                   "-filter_complex",
                   "[1:a]volume=0.6[a];[2:a]adelay=700:all=1[b];"
                   "[3:a]adelay=3800:all=1[c];"
                   "[a][b][c]amix=inputs=3:normalize=0,alimiter=limit=0.9[mix]",
                   "-map", "0:v", "-map", "[mix]", "-c:v", "copy", "-c:a", "aac",
                   "-t", DURATION, "-movflags", "+faststart", BUILD / f"preview-{variant}-audio.mp4")
        print(f"Built {name}: {preview}")
    (BUILD / "manifest.json").write_text(json.dumps({"fps": FPS, "variants": ["black", "white"],
        "close_seconds": 3.6, "fade_end_seconds": 4.6}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", action="store_true", help="mix supplied audio for desktop previews only")
    build(parser.parse_args().audio)

#!/usr/bin/env python3
"""Verify screenshot cuts, slide-in motion, assembly, and the logo-free final image."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 960, 540


def pixels(path, pixel_format="rgb24"):
    return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path),
                                    "-pix_fmt", pixel_format, "-f", "rawvideo", "pipe:1"])


def check_texture_motion(part, phase, face, panel):
    # Search for the actual RGB translation of an opaque screenshot piece.
    # Static masks and uniform opacity fades cannot match the diagnostic image.
    x0, y0, width, height = panel["bounds"]
    horizontal = panel["reveal"] in ("left", "right")
    limit = width if horizontal else height
    negative = panel["reveal"] in ("right", "down")
    def score(shift):
        if part == "left":
            xs, ys = range(5, min(324+shift, 324)-5, 16), range(305, 430, 19)
        elif part == "right":
            xs, ys = range(max(830, x0+shift+5), 954, 16), range(305, 430, 19)
        elif part == "top":
            xs, ys = range(400, 550, 19), range(5, min(height+shift-6, 440), 17)
        else:
            xs, ys = range(345, 615, 23), range(y0+shift+5, 535, 7)
        total = matched = 0
        for y in ys:
            for x in xs:
                source_x = x-x0-(shift if horizontal else 0)
                source_y = y-y0-(0 if horizontal else shift)
                if not (4 <= source_x < width-5 and 4 <= source_y < height-5):
                    continue
                source_i = (source_y*width+source_x)*4
                if face[source_i+3] != 255:
                    continue
                target_i = (y*WIDTH+x)*3
                total += 1
                matched += max(abs(phase[target_i+c]-face[source_i+c]) for c in range(3)) <= 2
        return matched/total if total >= 20 else -1
    shifts = range(-limit+1, 0) if negative else range(1, limit)
    stationary = score(0)
    best, shift = max((score(shift), shift) for shift in shifts)
    assert best > 0.95 and best-stationary > 0.2, (
        f"{part}: screenshot pixels did not slide: shift={shift}, match={best}, stationary={stationary}")
    print(f"  {part}: texture moved {shift}px, {best:.0%} pixel match")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--variant", choices=["white", "black"])
parser.add_argument("--check-texture-motion", action="store_true", help="probe RGB motion using the diagnostic color-coordinate image")
args = parser.parse_args()
manifest = json.loads((ROOT / "build/manifest.json").read_text())
assert manifest["mode"] == "sliding-textured-panels"
for variant in ([args.variant] if args.variant else ["white", "black"]):
    theme = ROOT / f"build/themes/titanfall-{variant}"
    prefix = ROOT / f"build/plymouth-{variant}"
    initial = pixels(str(prefix) + "-background.png")
    background = 255 if variant == "white" else 0
    assert len(initial) == WIDTH * HEIGHT * 3
    assert min(initial) == max(initial) == background, "The complete screenshot is visible before the pieces arrive"
    assembled = pixels(theme / "assembled.png")
    masks = {part: pixels(theme / f"mask-{part}.png") for part in manifest["panels"]}
    assert all(any(mask[i] for mask in masks.values()) for i in range(0, len(initial), 3)), "Panel coverage has a hole"
    bottom = manifest["panels"]["bottom"]["bounds"]
    shared_x = sorted({x for x, y in manifest["panels"]["top"]["polygon"] if y == bottom[1]})
    assert shared_x == [bottom[0], bottom[0]+bottom[2]], "Bottom panel width differs from middle panel"
    for part, panel in manifest["panels"].items():
        x0, y0, width, height = panel["bounds"]
        face = pixels(theme / f"face-{part}.png", "rgba")
        assert len(face) == width * height * 4
        checked = 0
        for y in range(height):
            for x in range(0, width, 7):
                local = (y * width + x) * 4
                source = ((y0+y) * WIDTH + x0+x) * 3
                assert abs(face[local+3] - masks[part][source]) <= 1, f"{part}: shape mask differs from screenshot cut"
                if face[local+3] == 255:
                    assert face[local:local+3] == assembled[source:source+3], f"{part}: face does not contain its actual screenshot pixels"
                    checked += 1
        assert checked > 100
        phase = pixels(str(prefix) + f"-phase-{part}.png")
        assert phase != initial and phase != assembled, f"{part}: missing partial slide-in frame"
        if args.check_texture_motion:
            motion_phase = pixels(str(prefix) + "-phase-top-motion.png") if part == "top" else phase
            check_texture_motion(part, motion_phase, face, panel)
    closed = pixels(str(prefix) + "-closed.png")
    for y in range(145, 320):
        start, end = (y*WIDTH+390)*3, (y*WIDTH+570)*3
        assert closed[start:end] == assembled[start:end], "The logo or an extra image remains in the main panel"
    final = pixels(str(prefix) + "-screenshot.png")
    assert final == assembled, "The pieces do not assemble into the complete screenshot after outlines fade"
    assert not (theme / "marauder-logo.png").exists()
    print(f"{variant}: blank start, screenshot-shaped pieces, slide-in phases, no logo, exact final assembly verified")

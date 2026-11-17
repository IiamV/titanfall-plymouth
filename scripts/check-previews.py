#!/usr/bin/env python3
"""Check fixed panel geometry, full coverage, sequential lighting, and final fade."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 960, 540


def pixels(path):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path),
                                    "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    assert len(data) == WIDTH * HEIGHT * 3, f"Unexpected image size: {path}"
    return data


def active(data, background):
    return {i for i in range(0, len(data), 3)
            if max(abs(channel - background) for channel in data[i:i+3]) > 8}


def emblem(data):
    colored = set()
    for y in range(145, 320):
        for x in range(390, 570):
            i = (y * WIDTH + x) * 3
            rgb = data[i:i+3]
            if max(rgb) - min(rgb) > 24:
                colored.add((x, y))
    assert colored, "The central/top-panel emblem is missing"
    center_x = (min(x for x, _ in colored) + max(x for x, _ in colored)) / 2
    center_y = (min(y for _, y in colored) + max(y for _, y in colored)) / 2
    assert abs(center_x - 480) <= 3 and abs(center_y - 234) <= 3, (
        f"Emblem is not centered on the main/top panel: {center_x}, {center_y}")
    return colored


manifest = json.loads((ROOT / "build/manifest.json").read_text())
assert manifest["mode"] == "stationary-light-up"
for variant in ("white", "black"):
    background = 255 if variant == "white" else 0
    masks = {name: pixels(ROOT / f"build/themes/titanfall-{variant}/mask-{name}.png")
             for name in ("left", "right", "top", "bottom")}
    assert all(any(mask[i] for mask in masks.values())
               for i in range(0, WIDTH * HEIGHT * 3, 3)), "Panel coverage has a hole"
    closed = pixels(ROOT / f"build/plymouth-{variant}-closed.png")
    final_geometry = active(closed, background)
    for part, mask in masks.items():
        phase = pixels(ROOT / f"build/plymouth-{variant}-phase-{part}.png")
        lit = active(phase, background)
        assert sum(bool(mask[i]) for i in lit) > 30, f"{variant}: {part} never lights up"
        # Illumination may change intensity, but must not create edges at new
        # coordinates. This fails if panels slide or rotate into their positions.
        assert len(lit - final_geometry) <= 30, f"{variant}: {part} geometry moved"
        if part == "top":
            assert emblem(phase) == emblem(closed), f"{variant}: emblem position changed"
    for x, y in emblem(closed):
        assert masks["top"][(y * WIDTH + x) * 3], "Emblem falls outside the main/top panel"
    final = pixels(ROOT / f"build/plymouth-{variant}-screenshot.png")
    assert min(final) == max(final) == background, f"{variant}: final frame is not plain"
    print(f"{variant}: full coverage, fixed panel positions, light-up, emblem, final fade verified")

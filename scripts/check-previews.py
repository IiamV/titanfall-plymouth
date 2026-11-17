#!/usr/bin/env python3
"""Check all rendered panel motions, top-panel logo placement, and final fade."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 960, 540


def pixels(path):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path),
                                    "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    assert len(data) == WIDTH * HEIGHT * 3, f"Unexpected screenshot size: {path}"
    return data


def changed(first, last, box):
    x0, y0, x1, y1 = box
    total = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * WIDTH + x) * 3
            total += first[i:i+3] != last[i:i+3]
    return total


def check_logo(data, variant):
    # Only the emblem has chromatic pixels. All clean panel lines are neutral.
    colored = []
    for y in range(230):
        for x in range(380, 580):
            i = (y * WIDTH + x) * 3
            rgb = data[i:i+3]
            if max(rgb) - min(rgb) > 24:
                colored.append((x, y))
    assert colored, f"{variant}: top-panel emblem is missing"
    center_x = (min(x for x, _ in colored) + max(x for x, _ in colored)) / 2
    center_y = (min(y for _, y in colored) + max(y for _, y in colored)) / 2
    assert abs(center_x - 480) <= 3, f"{variant}: emblem is not horizontally centered"
    # The central lower lip is 88px below the top plate's center. Detect its
    # long horizontal edge, rather than trusting animation timing or script values.
    horizontal = []
    for y in range(70, 245):
        count = 0
        for x in range(410, 550):
            i = (y * WIDTH + x) * 3
            rgb = data[i:i+3]
            neutral = max(rgb) - min(rgb) < 8
            contrast = max(rgb) < 140 if variant == "white" else min(rgb) > 115
            count += neutral and contrast
        if count >= 132:
            horizontal.append(y)
    assert horizontal, f"{variant}: top-panel lip is missing"
    assert abs((max(horizontal) - center_y) - 88) <= 6, (
        f"{variant}: emblem detached from top panel: lip={max(horizontal)}, center={center_y}")


for variant in ("white", "black"):
    closed = pixels(ROOT / f"build/plymouth-{variant}-closed.png")
    boxes = {"left": (0, 80, 250, 450), "right": (710, 80, 960, 450),
             "top": (250, 0, 710, 180), "bottom": (200, 360, 760, 540)}
    for part, box in boxes.items():
        moving = pixels(ROOT / f"build/plymouth-{variant}-phase-{part}.png")
        count = changed(moving, closed, box)
        assert count > 400, f"{variant}: {part} panel has no visible motion ({count} changed pixels)"
        if part == "top":
            check_logo(moving, variant)
    check_logo(closed, variant)
    final = pixels(ROOT / f"build/plymouth-{variant}-screenshot.png")
    background = 255 if variant == "white" else 0
    assert min(final) == max(final) == background, f"{variant}: final frame is not plain"
    print(f"{variant}: four panel motions, top-panel logo, final blank frame verified")

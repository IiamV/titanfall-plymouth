#!/usr/bin/env python3
"""Check native 4:3 and ultrawide screenshots for full layout and square emblems."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

for width, height in [(1024, 768), (1280, 540)]:
    prefix = ROOT / f"build/plymouth-black-{width}x{height}"
    def image(suffix):
        return subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(prefix) + suffix,
                                        "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"])
    baseline = image("-background.png")
    data = image("-closed.png")
    assert len(data) == len(baseline) == width * height * 3
    def ink(x, y):
        i = (y * width + x) * 3
        return max(abs(data[i+c] - baseline[i+c]) for c in range(3)) > 30
    # The packaged SDDM screenshot has its own white border, so compare edge
    # visibility directly; a difference from the background would be ambiguous.
    def visible(x, y):
        i = (y * width + x) * 3
        return min(data[i:i+3]) > 210
    for x in [0, width - 1]:
        assert sum(visible(x, y) for y in range(height)) > height * 0.9, "A side border was cropped"
    for y in [0, height - 1]:
        assert sum(visible(x, y) for x in range(width)) > width * 0.9, "A horizontal border was cropped"
    # This internal seam distinguishes responsive placement from a cropped
    # 16:9 image even when the backdrop supplies a matching outer border.
    seam_y = int(463 * height / 540)
    rows = [(y, [x for x in range(width//10, width*9//10) if ink(x, y)])
            for y in range(seam_y - 4, seam_y + 5)]
    _, seam = max(rows, key=lambda row: len(row[1]))
    assert len(seam) > (629-330) * width/960 * 0.9, "The bottom seam is missing"
    assert abs(min(seam) - 330*width/960) <= 3 and abs(max(seam) - 629*width/960) <= 3, "The panel layout was cropped instead of resized"
    center_x, center_y = width / 2, 234 * height / 540
    radius = int(80 * min(width/960, height/540))
    colored = []
    for y in range(max(0, int(center_y)-radius), min(height, int(center_y)+radius)):
        for x in range(max(0, int(center_x)-radius), min(width, int(center_x)+radius)):
            i = (y * width + x) * 3
            rgb = data[i:i+3]
            if max(rgb)-min(rgb) > 24 and max(abs(rgb[c]-baseline[i+c]) for c in range(3)) > 8:
                colored.append((x, y))
    assert colored, "The emblem was lost during resizing"
    left, right = min(x for x, _ in colored), max(x for x, _ in colored)
    top, bottom = min(y for _, y in colored), max(y for _, y in colored)
    assert abs((left+right)/2-center_x) <= 3 and abs((top+bottom)/2-center_y) <= 3
    assert abs((right-left)-(bottom-top)) <= 3, "The emblem was stretched"
    assert image("-screenshot.png") == baseline, "The background changed after the fade"
    print(f"{width}x{height}: uncropped panel borders, centered square emblem, preserved background")

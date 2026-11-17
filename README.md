# Titanfall Pilot Link for Plymouth

A cockpit-panel light-up sequence with sliding light reveals using image-generated artwork based on stills from the complete local `closing-pilot.mp4` reference. Four adjoining panel faces cover the full screen: left, right, a large central/top panel, and a narrow centered bottom panel. The emblem stays in the center of the large central/top panel. The light reveals sweep inward from the sides, down the main panel, and up the bottom panel. The artwork stays registered in place; all outlines and the emblem fade together at the end.

- `titanfall-white`: white panel faces, black outlines.
- `titanfall-black`: black panel faces, white outlines.

The selected artwork preserves the restored image's bottom-panel height and narrows its width to match the middle panel's lower edge. The left and right panel faces extend to the bottom of the screen. The central area is a panel face, not an open viewport.

The built-in image generator produced [the artwork](theme/panels/generated-panels-v2.png); [the selected prompt and reference details](theme/panels/generation-prompt-v2.txt) are saved alongside it. The build converts its monochrome outlines into per-panel alpha layers, removing faint paper grain during palette conversion. It does not edge-detect gameplay textures or add panel translation.

Illumination timings are recorded in `theme/lighting.json`. The build retains the full local reference duration (about 5.44 seconds), adds a 0.15-second hold, then fades all outlines and the emblem over 0.8 seconds. Original media is never trimmed or overwritten.

## Build and review before installing

Dependencies: Python 3, FFmpeg, ImageMagick, and Plymouth with its script plugin.

```bash
python3 scripts/build.py --audio
ffplay -autoexit build/preview-white.mp4
ffplay -autoexit build/preview-black.mp4
```

The native Plymouth theme and desktop previews use the same fixed layout and illumination keyframes. The emblem is revealed by the same sliding light front as the large central/top panel and remains anchored at its center.

Optional desktop previews with the supplied sound clips:

```bash
ffplay -autoexit build/preview-white-audio.mp4
ffplay -autoexit build/preview-black-audio.mp4
```

The custom desktop audio mix starts machine noise at 0 seconds, Marauder speech at 0.3 seconds, and `the-line.m4a` at 2.6 seconds. Plymouth's script interface has no audio playback API, so the boot themes are silent.

## Test actual Plymouth without installing

These commands use private user, mount, network, and PID namespaces. They temporarily expose the built theme and preview configuration inside the preview process only. They do not change the selected system theme or rebuild the initramfs. Logs and screenshots go under `build/`.

For a visible X11 or XWayland preview:

```bash
bash scripts/preview-plymouth.sh white 8
bash scripts/preview-plymouth.sh black 8
```

If user namespaces are restricted, `unshare` reports an error. Do not run the preview commands directly against a live boot daemon as a workaround.

For native headless checks, install Xvfb if needed (Arch/CachyOS package `xorg-server-xvfb`), then run:

```bash
bash scripts/preview-plymouth.sh --headless white 8
bash scripts/preview-plymouth.sh --headless black 8
python3 scripts/check-previews.py
```

The preview saves a separate `build/plymouth-<variant>-phase-<panel>.png` for left, right, top, and bottom illumination, a `closed.png` image once all panels are lit, and a final `screenshot.png` after the shared fade. The checker examines the rendered pixels to confirm full panel coverage, matching middle/bottom widths, a spatial sliding reveal rather than uniform fading, fixed outline coordinates, a centered emblem, and a completely plain final frame. Logs are overwritten by each run.

Optional authentication rendering check:

```bash
bash scripts/preview-plymouth.sh --headless --diagnostics white 10
bash scripts/preview-plymouth.sh --headless --diagnostics black 10
```

This displays a synthetic password prompt; do not enter a real password. It keeps the prompt visible through the final fade and removes it when the preview exits. This checks prompt rendering, not encrypted-root unlocking. Rerun normal headless previews before invoking the pixel checker, because diagnostic final screenshots deliberately contain a prompt.

## Install only after reviewing

No system installation has been performed. Choose one variant. These commands install it, activate it, and regenerate the initramfs through the existing Plymouth integration:

```bash
plymouth-set-default-theme > build/previous-theme.txt

# Substitute titanfall-black below to select the dark variant.
sudo cp -r build/themes/titanfall-white /usr/share/plymouth/themes/
sudo plymouth-set-default-theme -R titanfall-white
```

The inspected CachyOS setup already includes the `plymouth` hook in `/etc/mkinitcpio.conf` and `quiet splash` in the running kernel command line. This project edits neither. Check that regeneration succeeds before rebooting. Desktop previews cannot validate firmware framebuffer behavior, physical monitor layout, or real encrypted-root unlocking. Fast boots may end Plymouth before the animation finishes; the theme does not delay startup.

Restore the previous theme:

```bash
sudo plymouth-set-default-theme -R "$(cat build/previous-theme.txt)"
```

## Sources and checkpoints

The five supplied media files remain unchanged. `closing-pilot.mp4` is the complete lighting-sequence reference used by the build; the incomplete downloaded excerpt from the earlier implementation has been removed. `build/manifest.json` records the original video's duration, frame count, SHA-256, keyframes, and fade timing. Generated assets and previews are ignored by Git.

Implementation follows the [official Plymouth scripting reference](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/) and the installed script-theme examples. The Plymouth skill search found no dedicated skill. A TwelveLabs video-understanding skill was read in full and reviewed but not installed or invoked; reference inspection used local FFmpeg frame sheets instead.

All changes are saved in separate title-only conventional commits. Inspect a checkpoint without discarding work:

```bash
git log --oneline
git switch -c inspect-checkpoint COMMIT_HASH
```

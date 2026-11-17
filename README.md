# Titanfall Pilot Link for Plymouth

A clean, four-panel cockpit animation based on the complete local `closing-pilot.mp4` reference. Both side plates move, followed by the top and bottom plates. The Marauder emblem stays centered on the top plate and travels with it. All lines and the emblem fade away together at the end.

- `titanfall-white`: white background, black outlines.
- `titanfall-black`: black background, white outlines.

The artwork is a clean 2D interpretation of the cockpit silhouettes, not an edge-detected texture or gameplay-video playback. Keyframe timings are recorded in `theme/motion.json`. The build uses the full local video's duration (about 5.44 seconds), adds a 0.15-second hold, then fades every panel and the emblem together over 0.8 seconds. No part of the original media is trimmed or overwritten.

## Build and review before installing

Dependencies: Python 3, FFmpeg, ImageMagick, and Plymouth with its script plugin.

```bash
python3 scripts/build.py --audio
ffplay -autoexit build/preview-white.mp4
ffplay -autoexit build/preview-black.mp4
```

The source artwork is in `theme/panels/`. The native Plymouth theme and desktop previews use the same keyframes. The emblem is positioned relative to the top sprite, rather than independently in the center of the display.

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

The preview saves a separate `build/plymouth-<variant>-phase-<panel>.png` for left, right, top, and bottom motion, a `closed.png` image once all panels settle, and a final `screenshot.png` after the shared fade. The checker examines the rendered pixels to confirm all four panels move, the emblem remains centered on the moving top plate, and the final frame is completely plain. Logs are overwritten by each run.

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

The five supplied media files remain unchanged. `closing-pilot.mp4` is the sole motion reference used by the build; the incomplete downloaded excerpt from the earlier implementation has been removed. `build/manifest.json` records the original video's duration, frame count, SHA-256, keyframes, and fade timing. Generated assets and previews are ignored by Git.

Implementation follows the [official Plymouth scripting reference](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/) and the installed script-theme examples. The Plymouth skill search found no dedicated skill. A TwelveLabs video-understanding skill was read in full and reviewed but not installed or invoked; reference inspection used local FFmpeg frame sheets instead.

All changes are saved in separate title-only conventional commits. Inspect a checkpoint without discarding work:

```bash
git log --oneline
git switch -c inspect-checkpoint COMMIT_HASH
```

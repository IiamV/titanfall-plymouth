# Titanfall Pilot Link for Plymouth

A cockpit-panel light-up sequence with sliding light reveals using image-generated artwork based on stills from the complete local `closing-pilot.mp4` reference. Four adjoining panel faces cover the full screen: left, right, a large central/top panel, and a narrow centered bottom panel. The light reveals sweep inward from the sides, down the main panel, and up the bottom panel. The artwork stays registered in place; all outlines fade together at the end.

- `titanfall-white`: white panel faces, black outlines.
- `titanfall-black`: black panel faces, white outlines.

The selected artwork preserves the restored image's bottom-panel height and narrows its width to match the middle panel's lower edge. The left and right panel faces extend to the bottom of the screen. The central area is a panel face, not an open viewport.

The built-in image generator produced [the artwork](theme/panels/generated-panels-v2.png); [the selected prompt and reference details](theme/panels/generation-prompt-v2.txt) are saved alongside it. The build converts its monochrome outlines into per-panel alpha layers, removing faint paper grain during palette conversion. It does not edge-detect gameplay textures or add panel translation.

Illumination timings are recorded in `theme/lighting.json`. The build retains the full local reference duration (about 5.44 seconds), adds a 0.15-second hold, then fades all outlines over 0.8 seconds. Original media is never trimmed or overwritten.

## Build and review before installing

Dependencies: Python 3, FFmpeg, ImageMagick, and Plymouth with its script plugin.

```bash
python3 scripts/build.py --audio
ffplay -autoexit build/preview-white.mp4
ffplay -autoexit build/preview-black.mp4
```

The native Plymouth theme and desktop previews use the same fixed layout and illumination keyframes. The logo is omitted from the current build; the supplied original logo file remains unchanged.

Optional desktop previews with the supplied sound clips:

```bash
ffplay -autoexit build/preview-white-audio.mp4
ffplay -autoexit build/preview-black-audio.mp4
```

The custom desktop audio mix starts machine noise at 0 seconds, Marauder speech at 0.3 seconds, and `the-line.m4a` at 2.6 seconds. Plymouth's script interface has no audio playback API, so the boot themes are silent.

## Responsive layout and transparent backgrounds

Panel coordinates now fit the actual screen width and height independently, rather than cropping a fixed 16:9 layout. The layout recalculates when Plymouth reports a new viewport size. Native 4:3 and ultrawide renders are checked separately.

The panel PNGs contain transparent faces with visible outlines. Plymouth runs before the graphical login session, so transparency cannot reveal a live SDDM window or desktop underneath it. Instead, this project can copy the same wallpaper or a packaged SDDM screenshot into the Plymouth theme and show it behind the transparent outlines. See the [official Plymouth description](https://wiki.freedesktop.org/www/Software/Plymouth/) for its early-boot role.

Find the active installed theme's images without building or changing anything:

```bash
python3 scripts/sddm_background.py
python3 scripts/sddm_background.py --preview
```

Discovery reads the standard SDDM configuration locations, honors the configured theme directory and theme configuration overrides, and searches the active theme under `/usr/share/sddm/themes` or `/usr/local/share/sddm/themes`. `--preview` reads the theme metadata's `Screenshot` entry, with common installed preview filenames as fallbacks. If the requested image is not found, the command explains which theme and paths were checked and exits with an error; it does not silently choose another theme.

Use the installed theme's configured background:

```bash
python3 scripts/build.py --audio --sddm-background
```

Or use its packaged screenshot:

```bash
python3 scripts/build.py --audio --sddm-preview
ffplay -autoexit build/preview-black.mp4
```

On the inspected machine, WarGames provides `Background.png` (plain black) and `preview.png` (a packaged example login-screen screenshot). A packaged screenshot is a static image with nonfunctional example controls, not a capture of the current live greeter. Screenshots fit completely inside the viewport without cropping; wallpaper images fill it while preserving aspect ratio.

Use a custom desktop wallpaper instead:

```bash
python3 scripts/build.py --audio --background /absolute/path/to/wallpaper.jpg
```

Choose the black variant (white lines) for dark images, or the white variant (black lines) for light images. The selected image is copied into generated theme assets and remains visible after the outlines fade. It is a build-time snapshot: repeat the build and the installation/initramfs commands after changing the wallpaper. These options do not modify SDDM or desktop settings.

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
python3 scripts/build.py
bash scripts/preview-plymouth.sh --headless white 8
bash scripts/preview-plymouth.sh --headless black 8
python3 scripts/check-previews.py
```

The preview saves a separate `build/plymouth-<variant>-phase-<panel>.png` for left, right, top, and bottom illumination, a `closed.png` image once all panels are lit, and a final `screenshot.png` after the shared fade. The checker examines the rendered pixels to confirm full panel coverage, matching middle/bottom widths, a spatial sliding reveal rather than uniform fading, fixed outline coordinates, no logo, and restoration of the original background after the final fade. Logs are overwritten by each run.

For the dark SDDM screenshot and responsive layout checks:

```bash
python3 scripts/build.py --sddm-preview
bash scripts/preview-plymouth.sh --headless black 8
python3 scripts/check-previews.py --variant black
bash scripts/preview-plymouth.sh --headless black 8 1024x768
bash scripts/preview-plymouth.sh --headless black 8 1280x540
python3 scripts/check-layouts.py
python3 scripts/test-sddm-background.py
```

Non-default resolutions add the dimensions to screenshot filenames. The checks verify visible viewport borders, proportional middle/bottom placement, no logo, and an unchanged background after the final fade. Image-discovery tests cover configuration precedence, theme overrides, packaged screenshots, and missing files.

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

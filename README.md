# Titanfall Pilot Link for Plymouth

Two native Plymouth variants use the supplied Marauder emblem and animated angular cockpit lines. The video is a visual reference, never played during boot.

- `titanfall-white`: white background, black lines.
- `titanfall-black`: black background, white lines.
- The logo fades in at the center; the lines converge and close at 3.6 seconds.
- **The logo and lines fade out together from 3.8 to 4.6 seconds**, leaving the plain background until boot finishes.

The original logo colors are preserved in both variants. Password, question, and status callbacks remain available after the animation fades. Fast boots may end Plymouth before the sequence completes; the theme does not delay startup.

## Build and watch before installing

Run from this repository. Dependencies: Python 3, FFmpeg, ImageMagick, and Plymouth with its script plugin. CachyOS already has Plymouth configured on the machine inspected for this project.

```bash
python3 scripts/build.py --audio
ffplay -autoexit build/preview-white.mp4
ffplay -autoexit build/preview-black.mp4
```

Optional desktop previews with the supplied sound clips:

```bash
ffplay -autoexit build/preview-white-audio.mp4
ffplay -autoexit build/preview-black-audio.mp4
```

Audio is mixed for desktop previews only: machine noise starts at 0 seconds, Marauder speech at 0.7 seconds, and `the-line.m4a` at 3.8 seconds. Plymouth's script interface has no audio playback API, so the boot themes are silent. These timings are an original interpretation, not a verified reproduction of the YouTube reference.

## Test the actual Plymouth theme without installing

These commands use private user, mount, network, and PID namespaces. They temporarily expose the built theme and preview configuration **inside the preview process only**. They do not change the selected system theme or rebuild the initramfs. Preview logs and images are written under `build/`.

An X11 or XWayland `DISPLAY` is required for the visible preview:

```bash
bash scripts/preview-plymouth.sh white 10
bash scripts/preview-plymouth.sh black 10
```

If user namespaces are restricted, `unshare` will fail and report it. Do not run the commands directly on a live boot daemon as a workaround.

Headless native checks require Xvfb (Arch/CachyOS package `xorg-server-xvfb`):

```bash
bash scripts/preview-plymouth.sh --headless white 8
bash scripts/preview-plymouth.sh --headless black 8
```

These save `build/plymouth-<variant>-midpoint.png` during the animation and `build/plymouth-<variant>-screenshot.png` after the fade. The final image should be completely plain. Logs are overwritten by each run.

Optional authentication rendering check (synthetic password prompt; do not type a real password):

```bash
bash scripts/preview-plymouth.sh --headless --diagnostics white 10
bash scripts/preview-plymouth.sh --headless --diagnostics black 10
```

The diagnostic check saves an additional `build/plymouth-<variant>-prompt.png`, then reloads the theme to clear the synthetic prompt. This checks prompt rendering, not encrypted-root unlocking or a real boot.

## Install only after reviewing

No system installation has been performed. Choose **one** variant below. The following commands install and activate it, then regenerate the initramfs through Plymouth's existing system integration:

```bash
# Save the current theme name for rollback.
plymouth-set-default-theme > build/previous-theme.txt

# Choose titanfall-black here for the dark variant instead.
sudo cp -r build/themes/titanfall-white /usr/share/plymouth/themes/
sudo plymouth-set-default-theme -R titanfall-white
```

The inspected CachyOS setup already includes `plymouth` in `/etc/mkinitcpio.conf` and `quiet splash` in the running kernel command line. The project does not edit either setting. Check that the regeneration command succeeds before rebooting. A desktop/Xvfb preview cannot validate the firmware framebuffer, encrypted-root flow, or physical monitor layout during boot.

Restore the previously selected theme and rebuild the initramfs:

```bash
sudo plymouth-set-default-theme -R "$(cat build/previous-theme.txt)"
```

## Files and checkpoints

`theme/` contains the readable script template. `scripts/build.py` generates the two installable directories in `build/themes/` and the preview videos. Generated files are ignored by Git. Each theme uses a handful of small PNG sprites, with no video-frame sequence in the initramfs.

The supplied media remains unchanged in the repository. `git log --oneline` lists title-only conventional commits. To inspect any checkpoint without discarding current work:

```bash
git switch -c inspect-checkpoint COMMIT_HASH
```

Implementation follows the [official Plymouth scripting reference](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/) and the locally installed script theme. The requested skill search returned no Plymouth-specific skill; no third-party skill was installed. The YouTube reference could not be fetched during development, so the sequence follows the supplied assets and the requested black/white closing-and-fading behavior.

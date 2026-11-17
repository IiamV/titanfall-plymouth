# Titanfall Pilot Link for Plymouth

Two native Plymouth variants use the supplied Marauder emblem and contours sampled from the actual Titan cockpit closure at 28.6–29.4 seconds of the YouTube reference. The theme renders separate chassis, upper-hatch, and lower-plate sprites; gameplay footage is not played during boot.

- `titanfall-white`: white background, black lines.
- `titanfall-black`: black background, white lines.
- The logo fades in at the center. From 0.6 to 1.4 seconds, the upper hatch slides down and the lower plate slides up.
- **The logo and all cockpit lines fade out together from 1.65 to 2.45 seconds**, leaving the plain background until boot finishes.

The panel contours come from the reference video. Their separate vertical sprite translations recreate the visible closing movement; they do not reproduce the game’s full 3D hinge motion or its later display-reopening sequence.

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

Audio is mixed for desktop previews only: machine noise starts at 0 seconds, Marauder speech at 0.3 seconds, and `the-line.m4a` at 2.6 seconds. Plymouth's script interface has no audio playback API, so the boot themes are silent. The reference was downloaded and visually inspected frame by frame. Audio placement is a custom desktop-preview mix.

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

These save `build/plymouth-<variant>-midpoint.png` during movement, `build/plymouth-<variant>-closed.png` after the panels stop, and `build/plymouth-<variant>-screenshot.png` after the fade. The final image should be completely plain. Logs are overwritten by each run.

Optional authentication rendering check (synthetic password prompt; do not type a real password):

```bash
bash scripts/preview-plymouth.sh --headless --diagnostics white 10
bash scripts/preview-plymouth.sh --headless --diagnostics black 10
```

The diagnostic check saves an additional `build/plymouth-<variant>-prompt.png`, keeps the synthetic dialog visible through the final fade, and clears it when the preview exits. This checks prompt rendering, not encrypted-root unlocking or a real boot.

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

The supplied media remains unchanged in the repository. `assets/cockpit-close-reference.mp4` is a one-second, silent source excerpt from the linked reference; see `assets/README.md` for provenance. `git log --oneline` lists title-only conventional commits. To inspect any checkpoint without discarding current work:

```bash
git switch -c inspect-checkpoint COMMIT_HASH
```

Implementation follows the [official Plymouth scripting reference](https://wiki.freedesktop.org/www/Software/Plymouth/Scripts/) and the locally installed script theme. The requested skill search returned no Plymouth-specific skill; no third-party skill was installed. A later revision downloaded the YouTube reference with yt-dlp and inspected timestamped FFmpeg frame sheets. The TwelveLabs video-understanding skill was read in full and reviewed; it describes a hosted API and was not installed or invoked. The animation build runs locally with no hosted video service.

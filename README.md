# Titanfall Plymouth

Cockpit panels light up **left → middle → right → top → bottom**, revealing your SDDM picture or wallpaper. Fixed internal seams draw inward, then retract outward. No outer border or logo.

## Demos

| Black | White |
| --- | --- |
| ![Black SDDM demo](docs/demo/black.gif) | ![White SDDM demo](docs/demo/white.gif) |

[Black with sound](docs/demo/black-audio.mp4) · [White with sound](docs/demo/white-audio.mp4)

**Wallpaper with cyan lines and 1.25× speed**

![Wallpaper panel animation](docs/demo/wallpaper.gif)

[Wallpaper video](docs/demo/wallpaper.mp4) · [Example wallpaper](docs/demo/wallpaper.svg)

## Interactive setup

Needs **Python 3, FFmpeg, ImageMagick, and Plymouth's script plugin**.

```bash
git clone https://github.com/IiamV/titanfall-plymouth.git
cd titanfall-plymouth
./install.sh
```

Use arrow keys and Enter to choose **SDDM**, **Picture**, or **Custom**. SDDM and Picture show the exact image path beside the choice. Picture detects your desktop/WM wallpaper, then checks standard wallpaper folders (marked as a fallback). Custom asks for a path (leave it blank for no picture). Then choose colors and speed. The wizard builds a preview and offers installation afterward.

- Test without installation: `./install.sh --preview-only`
- Restore the previous theme: `./install.sh --restore`

Installation requests sudo only at the final step and uses `plymouth-set-default-theme -R`. Existing theme files and the previous selection are backed up locally. Builds work without the original reference media.

## Command-line options

```bash
python3 scripts/build.py --background docs/demo/wallpaper.svg \
  --panel-color '#0b1220' --line-color '#6ee7ff' --speed 1.25
ffplay -autoexit build/preview-custom.mp4
```

`--panel-color` sets solid panels/backdrop; wallpaper keeps its colors. `--line-color` sets the seams. Both accept `'#RGB'` or `'#RRGGBB'`. Speed ranges from `0.25–4`: `1.25` is faster, `0.75` is slower. Settings apply when rebuilding.

The picture is a snapshot, not live SDDM. Audio is optional in video previews; boot audio is not implemented. See [testing, audio, manual installation, and rollback](docs/DEVELOPMENT.md) for details.

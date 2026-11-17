#!/usr/bin/env python3
"""Find the active SDDM theme's installed background or packaged screenshot."""
import argparse
import configparser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


class SDDMImageNotFound(RuntimeError):
    pass


@dataclass(frozen=True)
class SDDMImage:
    path: Path
    theme: str
    kind: str


def read_ini(paths):
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.read([str(path) for path in paths if path.is_file()], encoding="utf-8-sig")
    return parser


def find_sddm_image(preview=False, root=Path("/")):
    root = Path(root)
    configs = []
    for directory in ("usr/lib/sddm/sddm.conf.d", "usr/local/lib/sddm/sddm.conf.d", "etc/sddm.conf.d"):
        configs.extend(sorted((root / directory).glob("*.conf")))
    configs.append(root / "etc/sddm.conf")
    settings = read_ini(configs)
    current = settings.get("Theme", "Current", fallback="").strip()
    if not current:
        raise SDDMImageNotFound("No active SDDM theme is configured in the standard sddm.conf locations. Use --background /path/to/image instead.")
    theme_dirs = []
    configured = settings.get("Theme", "ThemeDir", fallback="").strip()
    if configured:
        theme_dirs.append(root / configured.lstrip("/"))
    theme_dirs += [root / "usr/share/sddm/themes", root / "usr/local/share/sddm/themes"]
    theme = next((directory / current for directory in theme_dirs if (directory / current).is_dir()), None)
    if theme is None:
        raise SDDMImageNotFound(f"Active SDDM theme {current!r} was not found under: {', '.join(map(str, theme_dirs))}")
    metadata = read_ini([theme / "metadata.desktop"])
    config_name = metadata.get("SddmGreeterTheme", "ConfigFile", fallback="theme.conf")
    config_path = theme / config_name
    config = read_ini([config_path, Path(str(config_path) + ".user")])
    values = []
    if preview:
        values = [metadata.get("SddmGreeterTheme", "Screenshot", fallback=""), "preview.png", "screenshot.png"]
    else:
        for section in ["General"] + [section for section in config.sections() if section != "General"]:
            for key in ("background", "backgroundimage", "backgroundpath", "wallpaper", "wallpaperpath"):
                value = config.get(section, key, fallback="").strip()
                if value:
                    values.append(value)
        if not values:
            values = ["Background.png", "background.png", "background.jpg"]
    attempted = []
    extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".svg", ".gif", ".avif", ".tif", ".tiff"}
    for value in values:
        if not value:
            continue
        uri = urlparse(value)
        if uri.scheme and uri.scheme != "file":
            continue
        value = unquote(uri.path) if uri.scheme == "file" else value
        candidate = Path(value).expanduser()
        candidates = [root / str(candidate).lstrip("/")] if candidate.is_absolute() else [theme / candidate, config_path.parent / candidate]
        for candidate in candidates:
            attempted.append(str(candidate))
            if candidate.suffix.lower() in extensions and candidate.is_file():
                return SDDMImage(candidate.resolve(), current, "packaged theme screenshot" if preview else "configured theme background")
    kind = "packaged screenshot" if preview else "background image"
    raise SDDMImageNotFound(f"No local {kind} found for SDDM theme {current!r}. Checked: {', '.join(dict.fromkeys(attempted)) or 'no local image path configured'}. Use --background /path/to/image instead.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="find the packaged theme screenshot instead of its background")
    args = parser.parse_args()
    try:
        result = find_sddm_image(args.preview)
    except SDDMImageNotFound as error:
        parser.exit(2, f"SDDM image not found: {error}\n")
    print(f"{result.theme}: {result.kind}: {result.path}")

#!/usr/bin/env python3
"""Discover a local wallpaper without executing user configuration files."""
import argparse
import ast
import configparser
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from urllib.parse import unquote,urlparse
import xml.etree.ElementTree as ET

EXTENSIONS={'.png','.jpg','.jpeg','.webp','.svg','.bmp','.gif','.avif','.tif','.tiff','.jxl'}


class WallpaperNotFound(RuntimeError): pass


@dataclass(frozen=True)
class Wallpaper:
    path: Path
    source: str
    kind: str  # active, configured, or fallback


def query(command):
    if not shutil.which(command[0]): return ''
    try:
        return subprocess.run(command,check=True,capture_output=True,text=True,errors='replace',timeout=0.8).stdout.strip()
    except (OSError,subprocess.SubprocessError): return ''


def text_file(path):
    try:
        with path.open(errors='replace') as stream: return stream.read(1024*1024)
    except OSError: return ''


def ini(path):
    parser=configparser.ConfigParser(interpolation=None,strict=False)
    try: parser.read_string(text_file(path))
    except configparser.Error: return configparser.ConfigParser(interpolation=None)
    return parser


def expand(value,variables):
    return re.sub(r'\$(?:\{([\w]+)\}|([\w]+))',lambda m:variables.get(m[1] or m[2],m[0]),value)


def files_in(directory):
    # Bound depth and work; do not recursively follow wallpaper-directory links.
    visited=0
    if not directory.is_dir(): return
    try:
        for parent,dirs,files in os.walk(directory,followlinks=False):
            visited+=1
            if visited>500: return
            dirs[:]=sorted(d for d in dirs if not d.startswith('.'))
            if len(Path(parent).relative_to(directory).parts)>=3: dirs[:]=[]
            for name in sorted(files):
                visited+=1
                if visited>500: return
                path=Path(parent)/name
                if path.suffix.lower() in EXTENSIONS and path.is_file(): yield path
    except OSError: return


def find_wallpaper(home=None,root=Path('/'),env=None,runner=None):
    home=Path(home or Path.home()).resolve()
    root=Path(root).resolve()
    env=dict(os.environ if env is None else env)
    env['HOME']=str(home)
    runner=runner or query
    config=Path(expand(env.get('XDG_CONFIG_HOME',str(home/'.config')),env)).expanduser()
    state=Path(expand(env.get('XDG_STATE_HOME',str(home/'.local/state')),env)).expanduser()
    cache=Path(expand(env.get('XDG_CACHE_HOME',str(home/'.cache')),env)).expanduser()
    desktop=':'.join(env.get(k,'') for k in ('XDG_CURRENT_DESKTOP','XDG_SESSION_DESKTOP','DESKTOP_SESSION')).lower()

    def path_for(value,base=home,variables=None):
        value=value.strip()
        if not value: return None
        if value[:1] in ('\"',"'") and value[-1:]==value[:1]:
            try: value=ast.literal_eval(value)
            except (SyntaxError,ValueError): value=value[1:-1]
        if not isinstance(value,str): return None
        uri=urlparse(value)
        if uri.scheme:
            if uri.scheme!='file' or uri.netloc not in ('','localhost'): return None
            value=unquote(uri.path)
        value=expand(value,{**env,**(variables or {})})
        if value=='~' or value.startswith('~/'): value=str(home)+value[1:]
        path=Path(value)
        if not path.is_absolute(): path=base/path
        elif root!=Path('/') and not path.is_relative_to(home) and not path.is_relative_to(root): path=root/str(path).lstrip('/')
        return path

    def image(value,base=home,variables=None):
        path=path_for(value,base,variables)
        if path is None: return None
        if path.is_file() and (path.suffix.lower() in EXTENSIONS or path.resolve().suffix.lower() in EXTENSIONS): return path.resolve()
        if path.is_dir():
            for images in (path/'contents/images',path/'images'):
                if images.is_dir():
                    candidates=list(files_in(images))
                    def resolution(candidate):
                        match=re.search(r'(\d+)x(\d+)',candidate.stem)
                        return int(match[1])*int(match[2]) if match else 0
                    if candidates: return max(candidates,key=resolution).resolve()
            candidate=next(files_in(path),None)
            return candidate.resolve() if candidate else None
        # GNOME slideshow definitions and KDE image packages use containers.
        if path.is_file() and path.suffix.lower()=='.xml':
            try:
                document=ET.fromstring(text_file(path))
                for node in document.iter():
                    if node.tag in ('file','from','to','size') and node.text:
                        candidate=path_for(node.text,path.parent)
                        if candidate and candidate.is_file() and candidate.suffix.lower() in EXTENSIONS: return candidate.resolve()
            except ET.ParseError: pass
        return None

    def result(value,source,kind,base=home,variables=None):
        candidate=image(value,base,variables)
        return Wallpaper(candidate,source,kind) if candidate else None

    # Query actual running wallpaper backends before considering saved configs.
    for backend in ('swww','awww'):
        for line in runner([backend,'query']).splitlines():
            match=re.search(r'currently displaying:\s*(?:image:\s*)?(.+)',line)
            if match:
                found=result(match[1],backend,'active')
                if found: return found
    if 'hypr' in desktop or env.get('HYPRLAND_INSTANCE_SIGNATURE'):
        for line in runner(['hyprctl','hyprpaper','listactive']).splitlines():
            match=re.search(r'(?:wallpaper\s*[:=]\s*|\s=\s|\s->\s|:\s+)(.+)',line,re.I)
            found=result(match[1] if match else line,'Hyprpaper','active')
            if found: return found
    if any(name in desktop for name in ('gnome','ubuntu','unity','cinnamon','mate')):
        schemas=[]
        if any(name in desktop for name in ('gnome','ubuntu','unity')):
            dark='prefer-dark' in runner(['gsettings','get','org.gnome.desktop.interface','color-scheme'])
            schemas += [('org.gnome.desktop.background',key) for key in (('picture-uri-dark','picture-uri') if dark else ('picture-uri','picture-uri-dark'))]
        if 'cinnamon' in desktop: schemas.append(('org.cinnamon.desktop.background','picture-uri'))
        if 'mate' in desktop: schemas.append(('org.mate.background','picture-filename'))
        for schema,key in schemas:
            found=result(runner(['gsettings','get',schema,key]),schema,'active')
            if found: return found
    if 'xfce' in desktop:
        for line in runner(['xfconf-query','-c','xfce4-desktop','-lv']).splitlines():
            match=re.match(r'\S*/(?:last-image|image-path)\s+(.+)',line)
            if match:
                found=result(match[1],'Xfce','active')
                if found: return found

    def config_lines(path,variables=None,seen=None):
        variables=dict(env if variables is None else variables)
        seen=set() if seen is None else seen
        if path in seen or len(seen)>=25: return
        seen.add(path)
        for raw in text_file(path).splitlines():
            line=raw.strip()
            if not line or line.startswith('#'): continue
            line=line.split(' #',1)[0].strip()
            variable=re.match(r'(?:set\s+)?\$(\w+)\s*(?:=\s*|\s+)(.+)',line)
            if variable:
                variables[variable[1]]=expand(variable[2].strip().strip('\"\''),variables)
                continue
            include=re.match(r'(?:source\s*=|include\s+)\s*(.+)',line)
            if include:
                target=path_for(include[1],path.parent,variables)
                if target:
                    try:
                        paths=sorted(target.parent.glob(target.name))
                        for included in paths: yield from config_lines(included,variables,seen)
                    except (OSError,ValueError): pass
                continue
            yield line,path.parent,variables.copy()

    def hyprpaper():
        for line,base,variables in config_lines(config/'hypr/hyprpaper.conf'):
            match=re.match(r'path\s*=\s*(.+)',line)
            legacy=re.match(r'wallpaper\s*=\s*[^,]*,\s*(.+)',line)
            value=match[1] if match else legacy[1] if legacy else ''
            value=re.sub(r'^(?:contain|tile):','',value)
            if value: yield value,'Hyprpaper',base,variables

    def sway():
        for line,base,variables in config_lines(config/'sway/config'):
            try: tokens=shlex.split(line,comments=True)
            except ValueError: continue
            if tokens and tokens[0]=='output':
                for key in ('bg','background'):
                    if key in tokens and tokens.index(key)+1<len(tokens):
                        yield tokens[tokens.index(key)+1],'Sway',base,variables
            if 'swaybg' in tokens:
                for key in ('-i','--image'):
                    if key in tokens and tokens.index(key)+1<len(tokens):
                        yield tokens[tokens.index(key)+1],'swaybg',base,variables

    def waypaper():
        settings=ini(config/'waypaper/config.ini')
        use_state=any(settings.get(section,'use_xdg_state',fallback='').lower() in ('true','1','yes','on') for section in settings.sections())
        paths=([state/'waypaper/state.ini'] if use_state else [])+[config/'waypaper/config.ini']
        for path in paths:
            values=ini(path)
            for section in values.sections():
                value=values.get(section,'wallpaper',fallback='')
                if value: yield value,'Waypaper',path.parent,env

    def plasma():
        path=config/'plasma-org.kde.plasma.desktop-appletsrc'
        settings=ini(path)
        for section in settings.sections():
            if 'Wallpaper' in section and section.endswith('][General'):
                value=settings.get(section,'Image',fallback='')
                if value: yield value,'KDE Plasma',home,env

    def xfce():
        path=config/'xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml'
        try:
            for node in ET.fromstring(text_file(path)).iter('property'):
                if node.get('name') in ('last-image','image-path'):
                    yield node.get('value',''),'Xfce',home,env
        except ET.ParseError: pass

    def other_configs():
        for line in text_file(home/'.fehbg').splitlines():
            if line.lstrip().startswith('#'): continue
            try: tokens=shlex.split(line,comments=True)
            except ValueError: continue
            if tokens and Path(tokens[0]).name=='feh':
                for token in tokens[1:]:
                    if not token.startswith('-'): yield token,'feh',home,env
        settings=ini(config/'nitrogen/bg-saved.cfg')
        for section in settings.sections():
            yield settings.get(section,'file',fallback=''),'Nitrogen',home,env
        try:
            value=json.loads(text_file(cache/'wal/colors.json')).get('wallpaper','')
            if isinstance(value,str): yield value,'pywal',home,env
        except (ValueError,AttributeError): pass

    providers=[waypaper,hyprpaper,sway,plasma,xfce,other_configs]
    active=hyprpaper if 'hypr' in desktop else sway if 'sway' in desktop else plasma if any(x in desktop for x in ('kde','plasma')) else xfce if 'xfce' in desktop else None
    if active: providers=[active]+[provider for provider in providers if provider!=active]
    for provider in providers:
        for value,source,base,variables in provider():
            found=result(value,source,'configured',base,variables)
            if found: return found

    # Standard user locations precede distro-provided image collections.
    pictures=home/'Pictures'
    for line in text_file(config/'user-dirs.dirs').splitlines():
        if line.startswith('XDG_PICTURES_DIR='):
            pictures=path_for(line.split('=',1)[1]) or pictures
    for filename in ('.background-image','.wallpaper','wallpaper.png','wallpaper.jpg'):
        found=result(str(home/filename),'standard user location','fallback')
        if found: return found
    directories=[pictures/'Wallpapers',pictures/'wallpapers',pictures/'Backgrounds',home/'Wallpapers',home/'.local/share/backgrounds']
    directories += [root/path for path in ('usr/share/backgrounds','usr/local/share/backgrounds','usr/share/wallpapers','usr/share/hyprland','usr/share/xfce4/backdrops')]
    for directory in directories:
        candidate=next(files_in(directory),None)
        if candidate: return Wallpaper(candidate.resolve(),'default wallpaper folder','fallback')
    raise WallpaperNotFound('No local wallpaper found in the active session, saved desktop/WM configs, or standard wallpaper folders. Choose Custom to enter an image path.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true',help='print image path, source, and discovery kind as JSON')
    args=parser.parse_args()
    try: wallpaper=find_wallpaper()
    except WallpaperNotFound as error: parser.exit(2,str(error)+'\n')
    if args.json: print(json.dumps({'path':str(wallpaper.path),'source':wallpaper.source,'kind':wallpaper.kind}))
    else: print(f'{wallpaper.kind} ({wallpaper.source}): {wallpaper.path}')

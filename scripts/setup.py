#!/usr/bin/env python3
"""Interactive theme setup; privilege is requested only for installation."""
import argparse
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import termios
import time
import tty
import unicodedata
import uuid

from build import DEFAULT_SPEED, animation_speed, hex_color
from images import validate_image
from full_sequence import PROFILES, normalize
from sddm_background import SDDMImageNotFound, find_sddm_image
from wallpaper import WallpaperNotFound, find_wallpaper

ROOT = Path(__file__).resolve().parents[1]
THEMES = Path('/usr/share/plymouth/themes')
VARIANTS = {prefix+palette for prefix in ('','long-','semi-long-','full-') for palette in ('black','white','custom')}


def menu_lines(options, selected, columns):
    # Wrap explicitly and leave the last column unused: terminal autowrap
    # otherwise adds physical rows that cursor-up must also account for.
    limit=max(2,columns-1)
    labels=[f'  {"●" if i==selected else "○"} {option}' for i,option in enumerate(options)]
    labels.append('  ↑/↓ to move · Enter to select')
    rows=[]
    for label in labels:
        line=''
        width=0
        for character in label:
            size=0 if unicodedata.combining(character) else (2 if unicodedata.east_asian_width(character) in ('W','F') else 1)
            if width+size>limit:
                rows.append(line)
                line=''
                width=0
            line+=character
            width+=size
        rows.append(line)
    return rows


def choose(title, options, default=0):
    print(f'\n◆ {title}')
    if not (sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get('TERM')!='dumb'):
        for i,option in enumerate(options,1): print(f'  {i}. {option}')
        while True:
            answer=input(f'Choice [{default+1}]: ').strip()
            if not answer: return default
            if answer.isdigit() and 1<=int(answer)<=len(options): return int(answer)-1
            print(f'Enter a number from 1 to {len(options)}.')
    selected=default
    fd=sys.stdin.fileno()
    previous=termios.tcgetattr(fd)
    def render():
        try: columns=os.get_terminal_size(sys.stdout.fileno()).columns
        except (OSError,ValueError): columns=shutil.get_terminal_size().columns
        rows=menu_lines(options,selected,columns)
        sys.stdout.write('\r\033[2K'+'\n\r\033[2K'.join(rows))
        sys.stdout.flush()
        return len(rows)
    rendered_rows=render()
    try:
        tty.setcbreak(fd)
        while True:
            key=os.read(fd,1)
            if key==b'\x1b':
                sequence=b''
                while len(sequence)<2 and select.select([fd],[],[],0.08)[0]: sequence+=os.read(fd,1)
                key={b'[A':b'k',b'[B':b'j'}.get(sequence,b'')
            if key in (b'\r',b'\n'): break
            if key in (b'k',b'j'):
                selected=(selected+(1 if key==b'j' else -1))%len(options)
            elif key.isdigit() and 1<=int(key)<=len(options): selected=int(key)-1
            elif key==b'\x04': raise EOFError
            else: continue
            if rendered_rows>1: sys.stdout.write(f'\033[{rendered_rows-1}A')
            sys.stdout.write('\r\033[J')
            rendered_rows=render()
    finally:
        termios.tcsetattr(fd,termios.TCSADRAIN,previous)
        print()
    return selected


def ask(title, default='', validate=lambda value:value):
    while True:
        value=input(f'◇ {title}'+(f' [{default}]' if default else '')+': ').strip() or default
        try: return validate(value)
        except (ValueError,argparse.ArgumentTypeError) as error: print(f'  {error}')


def confirm(title):
    return input(f'◇ {title} [y/N]: ').strip().lower() in ('y','yes')


def image_path(value):
    return str(validate_image(value))


def collect_options(sequence='short'):
    sequence=normalize(sequence)
    try:
        sddm=str(find_sddm_image(preview=True).path.resolve())
        sddm_error=None
    except SDDMImageNotFound as error:
        sddm=None
        sddm_error=str(error)
    try:
        detected=find_wallpaper()
        picture=detected.path
        picture_error=None
        suffix=' — default-folder fallback' if detected.kind=='fallback' else ''
    except WallpaperNotFound as error:
        detected=None
        picture=None
        picture_error=str(error)
        suffix=''
    sources=[f'SDDM — {sddm or "not found"}',f'Picture — {picture or "not found"}{suffix}','Custom — enter an image path']
    while True:
        source=choose('Picture (optional)',sources)
        if source==0:
            if not sddm:
                print(f'  {sddm_error}\n  Choose Picture or Custom instead.')
                continue
            image=sddm
        elif source==1:
            if not picture or not picture.is_file():
                print(f'  {picture_error or f"Image not found: {picture}"}\n  Choose SDDM or Custom instead.')
                continue
            image=str(picture)
            print(f'  Wallpaper source: {detected.source} ({detected.kind})')
        else:
            image=ask('Custom image path (Enter for no picture)',
                      validate=lambda value:image_path(value) if value else None)
        # Freeze the displayed image path instead of detecting another image
        # later when the build starts.
        image_args=['--background',image] if image else []
        break
    palette=choose('Colors',['Black panels / white lines','White panels / black lines','Custom hex colors'])
    variant=('black','white','custom')[palette]
    color_args=[]
    panel_color,line_color=(('#000000','#ffffff'),('#ffffff','#000000'),(None,None))[palette]
    if variant=='custom':
        panel_color=ask('Panel / backdrop hex color','#0b1220',hex_color)
        line_color=ask('Line hex color (or auto)','auto',lambda value:'auto' if value.lower()=='auto' else hex_color(value))
        color_args=['--panel-color',panel_color]
        if line_color!='auto': color_args+=['--line-color',line_color]
    speed_choice=choose('Animation speed',['Default — 1.25×','Slower — 1×','Slower — 0.75×','Custom speed'])
    speed=(DEFAULT_SPEED,1,0.75)[speed_choice] if speed_choice<3 else ask('Custom speed (0.25–4; lower is slower)',str(DEFAULT_SPEED),animation_speed)
    opening_color=opening_picture=None
    opening_args=[]
    if sequence!='short':
        opening_default=image or str(ROOT/'docs/demo/wallpaper.svg')
        opening_choice=choose('Outside / cockpit view',['Solid color',f'Picture — {opening_default}'])
        if opening_choice==0:
            opening_color=ask('Opening hex color',panel_color or '#0b1220',hex_color)
            opening_args=['--opening-color',opening_color]
        else:
            opening_picture=ask('Opening picture path',opening_default,image_path)
            opening_args=['--opening-picture',opening_picture]
        variant=sequence+'-'+variant
    command=[sys.executable,str(ROOT/'scripts/build.py'),*image_args,*color_args,'--speed',str(speed),'--sequence',sequence,*opening_args]
    return {'variant':variant,'sequence':sequence,'picture':image,'panel_color':panel_color,'line_color':line_color,'speed':speed,
            'opening_color':opening_color,'opening_picture':opening_picture,'command':command}


def check_dependencies():
    missing=[name for name in ('ffmpeg','ffprobe','magick') if not shutil.which(name)]
    if missing: raise RuntimeError('Install these dependencies first: '+', '.join(missing))


def build_theme(options):
    check_dependencies()
    output=ROOT/'build'
    output.mkdir(exist_ok=True)
    log=output/'setup-build.log'
    print('\n◇ Building theme and video preview…',flush=True)
    with log.open('w') as stream:
        process=subprocess.Popen(options['command'],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        spinner='◐◓◑◒'
        step=0
        try:
            while process.poll() is None:
                if sys.stdout.isatty():
                    print(f'\r  {spinner[step%4]} Building…',end='',flush=True)
                    step+=1
                time.sleep(0.1)
        except KeyboardInterrupt:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            raise
    if sys.stdout.isatty(): print('\r\033[2K',end='')
    if process.returncode:
        print('\n'.join(log.read_text().splitlines()[-8:]))
        raise RuntimeError(f'Build failed. Details: {log}')
    (output/'setup-options.json').write_text(json.dumps(options,indent=2)+'\n')
    return output/f'preview-{options["variant"]}.mp4'


def run_privileged(command):
    prefix=[] if os.geteuid()==0 else ['sudo']
    if prefix and not shutil.which('sudo'): raise RuntimeError('sudo is required to install. Build output is ready for manual installation.')
    subprocess.run(prefix+command,check=True)


def history_path(): return ROOT/'build/install-history.json'


def read_history():
    path=history_path()
    if not path.exists(): return []
    history=json.loads(path.read_text())
    if not isinstance(history,list): raise RuntimeError(f'Invalid install history: {path}')
    return history


def save_history(history):
    path=history_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(history,indent=2)+'\n')
    temporary.replace(path)


def check_theme_name(name):
    if not re.fullmatch(r'[A-Za-z0-9_.][A-Za-z0-9_.-]*',name) or name in ('.','..'):
        raise RuntimeError('Invalid previous theme name; installation stopped.')
    return name


def restore_entry(entry):
    theme=entry['theme']
    if theme not in {f'titanfall-{v}' for v in VARIANTS}: raise RuntimeError('Invalid installed theme in history.')
    previous=check_theme_name(entry['previous'])
    if entry.get('backup'):
        base=(ROOT/'build/install-backups').resolve()
        backup=(ROOT/entry['backup']).resolve()
        if not backup.is_relative_to(base) or not backup.is_dir(): raise RuntimeError('Theme backup is missing or outside the backup directory.')
        destination=THEMES/theme
        if destination.is_symlink() or (destination.exists() and any(path.is_symlink() for path in destination.rglob('*'))):
            raise RuntimeError('The installed theme contains symlinks; restore stopped.')
        run_privileged(['cp','-r','--',str(backup)+'/.',str(destination)])
    run_privileged(['plymouth-set-default-theme','-R',previous])


def install_theme(variant):
    if variant not in VARIANTS: raise RuntimeError('Unknown theme variant.')
    if not shutil.which('plymouth-set-default-theme'):
        raise RuntimeError('Automatic installation needs plymouth-set-default-theme with -R support. Use the generated theme for manual installation on this distribution.')
    name=f'titanfall-{variant}'
    source=ROOT/'build/themes'/name
    if not source.is_dir() or not all((source/f'{name}.{extension}').is_file() for extension in ('plymouth','script')) or any(path.is_symlink() for path in source.rglob('*')):
        raise RuntimeError('Generated theme is missing or contains symlinks. Rebuild it before installing.')
    previous=check_theme_name(subprocess.check_output(['plymouth-set-default-theme'],text=True).strip())
    destination=THEMES/name
    if destination.is_symlink() or (destination.exists() and any(path.is_symlink() for path in destination.rglob('*'))):
        raise RuntimeError('The destination theme contains symlinks; installation stopped.')
    backup=None
    if destination.exists():
        backup=ROOT/'build/install-backups'/uuid.uuid4().hex/name
        shutil.copytree(destination,backup,symlinks=True)
    entry={'theme':name,'previous':previous,'backup':str(backup.relative_to(ROOT)) if backup else None}
    history=read_history()
    history.append(entry)
    # Persist rollback information before any privileged mutation.
    save_history(history)
    try:
        run_privileged(['install','-d',str(destination)])
        run_privileged(['cp','-r','--',str(source)+'/.',str(destination)])
        run_privileged(['plymouth-set-default-theme','-R',name])
    except (Exception,KeyboardInterrupt):
        print('\nInstallation did not finish. Restoring the previous theme…')
        try:
            restore_entry(entry)
            save_history(history[:-1])
        except (Exception,KeyboardInterrupt):
            print('Automatic restore did not finish. Rollback information is saved. Run: ./install.sh --restore')
        raise
    print(f'\n✓ Installed {name}. Previous theme: {previous}.')
    print('  Restore later: ./install.sh --restore')


def restore_last():
    if not shutil.which('plymouth-set-default-theme'): raise RuntimeError('plymouth-set-default-theme is required to restore the previous theme.')
    history=read_history()
    if not history: raise RuntimeError('No installation to restore in this checkout.')
    entry=history[-1]
    restore_entry(entry)
    save_history(history[:-1])
    print(f'✓ Restored {entry["previous"]}.')


def main():
    parser=argparse.ArgumentParser(description='Interactive Titanfall Plymouth setup: picture, colors, speed, preview, and optional installation.')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--preview-only',action='store_true',help='build and optionally preview; never offer system installation')
    mode.add_argument('--restore',action='store_true',help='restore the theme used before the last installation from this checkout')
    args=parser.parse_args()
    if args.restore:
        if confirm('Restore the previous theme and rebuild initramfs?'): restore_last()
        return
    print('\n╭ Titanfall Plymouth\n╰ Configure · preview · install')
    check_dependencies()
    while True:
        sequence=('short','semi-long','long')[choose('Sequence',['Short — panel light-up','Semi-long — cockpit closing + light-up','Long — outside approach, typing, closing + light-up'])]
        if sequence!='short' and not (ROOT/PROFILES[sequence]).is_file():
            print(f'  {sequence.title()} needs {PROFILES[sequence]} in the project folder. Choose Short or restore that local file.')
            continue
        break
    options=collect_options(sequence)
    print(f'\n◇ Ready to build\n  Picture: {options["picture"] or "none (solid panels)"}\n  Colors: {options["panel_color"]} / {options["line_color"]}\n  Speed: {options["speed"]:g}×')
    if options.get('sequence','short')!='short': print('  Cockpit view: '+str(options['opening_picture'] or options['opening_color']))
    preview=build_theme(options)
    print(f'✓ Built titanfall-{options["variant"]}\n  Preview: {preview}')
    print('  Repeat: '+shlex.join(options['command']))
    if confirm('Open the video preview now?'):
        if shutil.which('ffplay') and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            subprocess.run(['ffplay','-autoexit',str(preview)],check=True)
        else:
            print('  Open this on a graphical desktop: '+shlex.join(['ffplay','-autoexit',str(preview)]))
    if args.preview_only:
        print('✓ Preview-only run complete. System theme unchanged.')
    elif confirm(f'Install titanfall-{options["variant"]} and rebuild initramfs?'):
        install_theme(options['variant'])
    else:
        print('✓ Build complete. System theme unchanged.')


if __name__=='__main__':
    try: main()
    except (KeyboardInterrupt,EOFError):
        print('\nSetup cancelled.',file=sys.stderr)
        sys.exit(130)
    except (RuntimeError,OSError,ValueError,subprocess.CalledProcessError) as error:
        print(f'\nSetup stopped: {error}',file=sys.stderr)
        sys.exit(1)

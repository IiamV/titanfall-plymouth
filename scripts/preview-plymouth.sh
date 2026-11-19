#!/usr/bin/env bash
# Preview in private mount/network/PID namespaces; never select a system theme.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ${1:-} != --inside ]]; then
    if [[ ! -f "$ROOT/build/manifest.json" ]]; then
        echo 'Build first: python3 scripts/build.py' >&2
        exit 1
    fi
    exec unshare --user --map-root-user --mount --net --pid --fork --mount-proc \
        bash "$0" --inside "$@"
fi
shift
headless=false
diagnostics=false
while [[ ${1:-} == --* ]]; do
    case $1 in
        --headless) headless=true ;;
        --diagnostics) diagnostics=true ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done
variant=${1:-white}
[[ $variant =~ ^((full|long|semi-long)-)?(black|white|custom)$ ]] || { echo 'Variant must be black, white, custom, or long-/semi-long- variants' >&2; exit 1; }
if (( $# )); then shift; fi
manifest="$ROOT/build/manifest-short.json"
if [[ $variant == full-* ]]; then manifest="$ROOT/build/manifest-full.json";
elif [[ $variant == semi-long-* ]]; then manifest="$ROOT/build/manifest-semi-long.json";
elif [[ $variant == long-* ]]; then manifest="$ROOT/build/manifest-long.json"; fi
if [[ ! -f $manifest ]]; then manifest="$ROOT/build/manifest.json"; fi
seconds=${1:-$(python3 -c 'import json,math,sys; print(max(8,math.ceil(json.load(open(sys.argv[1]))["preview_duration"])+1))' "$manifest")}
resolution=${2:-960x540}
[[ $resolution =~ ^[1-9][0-9]{1,3}x[1-9][0-9]{1,3}$ ]] || { echo 'Invalid preview resolution' >&2; exit 1; }
capture_prefix="$ROOT/build/plymouth-$variant"
if [[ $resolution != 960x540 ]]; then capture_prefix+="-$resolution"; fi
[[ $seconds =~ ^[0-9]+$ ]] && (( seconds >= 8 && seconds <= 120 )) || {
    echo 'Usage: scripts/preview-plymouth.sh [--headless] [--diagnostics] [black|white|custom] [seconds: 8..120] [WIDTHxHEIGHT]' >&2; exit 1;
}
mount --make-rprivate /
# ThemeDir is supported by Plymouth; bind only a private daemon configuration.
config=$(mktemp "$ROOT/build/preview-config.XXXXXX")
cat > "$config" <<CONFIG
[Daemon]
Theme=titanfall-$variant
ThemeDir=$ROOT/build/themes
ShowDelay=0
DeviceTimeout=1
CONFIG
mount --bind "$config" /etc/plymouth/plymouthd.conf
mount --bind "$ROOT/build/themes" /usr/share/plymouth/themes
mount -t tmpfs tmpfs /run/plymouth
xvfb_pid=
daemon_pid=
framebuffer=
cleanup() {
    plymouth quit >/dev/null 2>&1 || true
    if [[ -n $daemon_pid ]]; then kill "$daemon_pid" 2>/dev/null || true; fi
    if [[ -n $xvfb_pid ]]; then kill "$xvfb_pid" 2>/dev/null || true; fi
    rm -f -- "$config"
    if [[ -n $framebuffer ]]; then rm -rf -- "$framebuffer"; fi
}
trap cleanup EXIT INT TERM
if $headless; then
    command -v Xvfb >/dev/null || { echo 'Headless preview needs Xvfb' >&2; exit 1; }
    # Namespace has its own X11 socket directory, so display :99 cannot collide.
    mount -t tmpfs tmpfs /tmp
    framebuffer=$(mktemp -d "$ROOT/build/preview-framebuffer.XXXXXX")
    Xvfb :99 -screen 0 "${resolution}x24" -fbdir "$framebuffer" -nolisten tcp > "$ROOT/build/xvfb.log" 2>&1 &
    xvfb_pid=$!
    export DISPLAY=:99
    unset XAUTHORITY
    sleep 1
else
    display_number=${DISPLAY:-}
    display_number=${display_number#*:}
    display_number=${display_number%%.*}
    [[ -n ${DISPLAY:-} && -S /tmp/.X11-unix/X${display_number} ]] || {
        echo 'An X11/XWayland DISPLAY is required; use --headless for a smoke test.' >&2
        exit 1
    }
fi
plymouthd --no-daemon --debug --debug-file="$ROOT/build/plymouth-preview.log" \
    --no-boot-log --pid-file=/run/plymouth/preview.pid \
    --kernel-command-line='quiet splash' > "$ROOT/build/plymouth-daemon.log" 2>&1 &
daemon_pid=$!
ready=false
for ((i=0; i<50; i++)); do
    if plymouth --ping; then ready=true; break; fi
    sleep 0.1
done
$ready || { echo 'Plymouth did not start; inspect build/plymouth-preview.log' >&2; exit 1; }
plymouth show-splash
capture() {
    if $headless && command -v magick >/dev/null; then
        # Copy Xvfb's live framebuffer immediately. ImageMagick's interactive
        # import waits long enough to miss the short top/bottom phases.
        cp -- "$framebuffer/Xvfb_screen0" "$framebuffer/$1.xwd"
    fi
}
preview_started=$(python3 -c 'import time; print(time.monotonic())')
wait_until() {
    python3 -c 'import sys,time; time.sleep(max(0,float(sys.argv[1])+float(sys.argv[2])-time.monotonic()))' "$preview_started" "$1"
}
if [[ $variant == *-black || $variant == *-white || $variant == *-custom ]]; then capture intro-start; else capture background; fi
while read -r moment label; do
    wait_until "$moment"
    if $headless && [[ $label == background && $variant == *-* ]]; then
        preview_started=$(python3 "$ROOT/scripts/anchor-preview.py" "$framebuffer/Xvfb_screen0" "$manifest" "$framebuffer/background.xwd")
    else
        capture "$label"
    fi
done < <(python3 - "$manifest" <<'PYPLAN'
import json,sys
m=json.load(open(sys.argv[1])); lines=m['lines']
events=[]
for fraction,label in [(0.15,'entrance-early'),(0.60,'entrance-late')]:
    events.append((lines['entrance_start']+fraction*lines['entrance_duration'],label))
events.append((lines['entrance_end']+0.03,'lines-ready'))
for name,panel in m['panels'].items():
    start,end=panel['keys'][-2][0],panel['keys'][-1][0]
    events.append((start+0.45*(end-start),'phase-'+name))
events.append((m['assembly_time']+0.05,'closed'))
for fraction,label in [(0.25,'exit-early'),(0.75,'exit-late')]:
    events.append((lines['exit_start']+fraction*lines['exit_duration'],label))
offset=m.get('timeline_offset',0)
events=[(moment+offset,label) for moment,label in events]
if offset:
    events.extend([(moment,'intro-'+label) for label,moment in m['intro']['checkpoints'].items()])
    # Start watching before the handoff so helper startup cannot miss the
    # brief blank interval on the shorter clip.
    events.append((max(offset-0.1,m['intro']['checkpoints']['black']+0.01),'background'))
for moment,label in sorted(events): print(moment,label)
PYPLAN
)
if $diagnostics; then
    plymouth display-message --text='PILOT LINK // diagnostic message'
    # Synthetic prompt: never enter a real password during this preview.
    plymouth ask-for-password --prompt='TEST ONLY: unlock simulation' \
        --command=/usr/bin/true --dont-pause-progress > /dev/null 2>&1 &
    prompt_pid=$!
    sleep 2
    capture prompt
    # Keep the diagnostic dialog active to verify it survives the final fade.
    kill "$prompt_pid" 2>/dev/null || true
    plymouth hide-message --text='PILOT LINK // diagnostic message'
fi
wait_until "$seconds"
capture screenshot
if $headless && command -v magick >/dev/null; then
    for snapshot in "$framebuffer"/*.xwd; do
        label=${snapshot##*/}; label=${label%.xwd}
        magick "xwd:$snapshot" "$capture_prefix-$label.png"
    done
fi
plymouth quit
wait "$daemon_pid"
daemon_pid=
if rg -i 'parser error|parse error|syntax error|execution error|could not parse|failed to (load|execute).*script' \
    "$ROOT/build/plymouth-preview.log"; then
    echo 'Plymouth script error; inspect the log.' >&2; exit 1
fi
echo "Preview finished; log: $ROOT/build/plymouth-preview.log"

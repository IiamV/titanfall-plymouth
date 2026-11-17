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
[[ $variant == black || $variant == white ]] || { echo 'Variant must be black or white' >&2; exit 1; }
if (( $# )); then shift; fi
seconds=${1:-12}
resolution=${2:-960x540}
[[ $resolution =~ ^[1-9][0-9]{1,3}x[1-9][0-9]{1,3}$ ]] || { echo 'Invalid preview resolution' >&2; exit 1; }
capture_prefix="$ROOT/build/plymouth-$variant"
if [[ $resolution != 960x540 ]]; then capture_prefix+="-$resolution"; fi
[[ $seconds =~ ^[0-9]+$ ]] && (( seconds >= 8 && seconds <= 120 )) || {
    echo 'Usage: scripts/preview-plymouth.sh [--headless] [--diagnostics] [black|white] [seconds: 8..120] [WIDTHxHEIGHT]' >&2; exit 1;
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
cleanup() {
    plymouth quit >/dev/null 2>&1 || true
    if [[ -n $daemon_pid ]]; then kill "$daemon_pid" 2>/dev/null || true; fi
    if [[ -n $xvfb_pid ]]; then kill "$xvfb_pid" 2>/dev/null || true; fi
    rm -f -- "$config"
}
trap cleanup EXIT INT TERM
if $headless; then
    command -v Xvfb >/dev/null || { echo 'Headless preview needs Xvfb' >&2; exit 1; }
    # Namespace has its own X11 socket directory, so display :99 cannot collide.
    mount -t tmpfs tmpfs /tmp
    Xvfb :99 -screen 0 "${resolution}x24" -nolisten tcp > "$ROOT/build/xvfb.log" 2>&1 &
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
        magick import -window root "$capture_prefix-$1.png"
    fi
}
preview_started=$(python3 -c 'import time; print(time.monotonic())')
wait_until() {
    python3 -c 'import sys,time; time.sleep(max(0,float(sys.argv[1])+float(sys.argv[2])-time.monotonic()))' "$preview_started" "$1"
}
capture background
wait_until 0.34
capture phase-top
wait_until 0.72
capture phase-left
wait_until 1.03
capture phase-middle
wait_until 1.1
capture phase-right
wait_until 1.58
capture phase-bottom
wait_until 1.82
capture closed
wait_until 2.15
capture line-early
wait_until 2.55
capture line-late
wait_until 3.05
capture lit
if $diagnostics; then
    plymouth display-message --text='PILOT LINK // diagnostic message'
    # Synthetic prompt: never enter a real password during this preview.
    plymouth ask-for-password --prompt='TEST ONLY: unlock simulation' \
        --command=/usr/bin/true --dont-pause-progress > /dev/null 2>&1 &
    prompt_pid=$!
    sleep 2
    if $headless && command -v magick >/dev/null; then
        magick import -window root "$capture_prefix-prompt.png"
    fi
    # Keep the diagnostic dialog active to verify it survives the final fade.
    kill "$prompt_pid" 2>/dev/null || true
    plymouth hide-message --text='PILOT LINK // diagnostic message'
fi
wait_until "$seconds"
if $headless && command -v magick >/dev/null; then
    magick import -window root "$capture_prefix-screenshot.png"
fi
plymouth quit
wait "$daemon_pid"
daemon_pid=
if rg -i 'parser error|parse error|syntax error|execution error|could not parse|failed to (load|execute).*script' \
    "$ROOT/build/plymouth-preview.log"; then
    echo 'Plymouth script error; inspect the log.' >&2; exit 1
fi
echo "Preview finished; log: $ROOT/build/plymouth-preview.log"

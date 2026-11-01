#!/usr/bin/env bash
# BOOKMARK SYNC, END TO END, on the nas.lan emulator: PosterFox for Android paired with a throwaway PosterChan
# account against a throwaway relay. It proves both directions with the app's real bookmark storage:
#   desktop -> phone   a bookmark sealed and published as a paired desktop would (seed) lands in the app's bookmarks;
#   phone -> desktop   a bookmark made in the app reaches the relay as a pcai:bm event that opens with the vault key.
# Pairing goes through the extension's own Pair screen, driven by its accessibility tree (uiautomator), never by
# coordinates. The relay is tools/test_relay.py on nas, which the emulator reaches as 10.0.2.2.
#
#   tools/bookmark_roundtrip.sh path/to/posterfox.apk path/to/posterchan/extension
#   exit 0 = both directions proven; 1 = a direction failed; 2 = could not run
set -uo pipefail
APK=${1:?apk}; EXT=${2:?posterchan extension dir}
HERE=$(cd "$(dirname "$0")" && pwd)
NAS=${PC_EMU_HOST:-nas.lan}; PORT_RELAY=7788
OUT=/tmp/pf-rt/$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
node "$HERE/roundtrip_fixture.mjs" make "$EXT" "ws://10.0.2.2:$PORT_RELAY" "$OUT/fx" || exit 2
LOCK=android-sdk-emu/run.lock
until ssh "$NAS" "mkdir ~/$LOCK 2>/dev/null && echo '$(hostname) pid=$$ posterfox-roundtrip since=$(date +%s)' > ~/$LOCK/owner"; do
  echo "emulator busy: $(ssh "$NAS" "cat ~/$LOCK/owner" 2>/dev/null) -- waiting"; sleep 20
done
trap 'ssh "$NAS" "pkill -f pf-rt-relay; rm -rf ~/$LOCK" 2>/dev/null' EXIT
ssh "$NAS" 'mkdir -p ~/android-sdk-emu/pf/rt' || exit 2
scp -q "$APK" "$NAS:android-sdk-emu/pf/posterfox.apk" && scp -q "$HERE/test_relay.py" "$OUT/fx/seed.jsonl" "$OUT/fx/code.txt" \
  "$NAS:android-sdk-emu/pf/rt/" || exit 2
cat > "$OUT/run.sh" <<'REMOTE'
set -uo pipefail
E=$HOME/android-sdk-emu; RT=$E/pf/rt
PY=$HOME/posterchanai/venv/bin/python        # nas's PosterChan venv has websockets; the system python does not
export HOME=$E/home ANDROID_HOME=$E/sdk ANDROID_SDK_ROOT=$E/sdk ANDROID_USER_HOME=$E/user ANDROID_AVD_HOME=$E/avd
export ANDROID_ADB_SERVER_PORT=5137
PORT=5580; ADB="$ANDROID_HOME/platform-tools/adb -s emulator-$PORT"; R=$E/pf/rt/results; rm -rf "$R"; mkdir -p "$R"
: > "$RT/received.jsonl"
( exec -a pf-rt-relay "$PY" "$RT/test_relay.py" 7788 "$RT/seed.jsonl" "$RT/received.jsonl" > "$R/relay.txt" 2>&1 ) &
EMU_PID=
cleanup() {
  trap - EXIT INT TERM HUP
  pkill -f pf-rt-relay 2>/dev/null
  if [ -n "$EMU_PID" ] && kill -0 "$EMU_PID" 2>/dev/null; then
    $ADB emu kill >/dev/null 2>&1 || true
    for _ in $(seq 1 20); do kill -0 "$EMU_PID" 2>/dev/null || break; sleep 0.5; done
    kill -TERM "$EMU_PID" 2>/dev/null; sleep 2; kill -KILL "$EMU_PID" 2>/dev/null
    pkill -KILL -f "qemu-system-x86_64.*-avd pc34" 2>/dev/null || true
  fi
  "$ANDROID_HOME/platform-tools/adb" kill-server >/dev/null 2>&1 || true
  echo "EMULATOR_STOPPED"
}
trap cleanup EXIT INT TERM HUP
nice -n 19 ionice -c3 timeout --kill-after=30s 30m "$ANDROID_HOME/emulator/emulator" -avd pc34 \
  -port $PORT -no-window -no-audio -no-boot-anim -no-snapshot -wipe-data -no-snapshot-save \
  -gpu swangle -camera-back none -memory 3072 -cores 4 > "$R/emulator-console.txt" 2>&1 < /dev/null &
EMU_PID=$!
"$ANDROID_HOME/platform-tools/adb" start-server >/dev/null 2>&1
for _ in $(seq 1 300); do
  kill -0 "$EMU_PID" 2>/dev/null || { echo "EMULATOR_DIED"; exit 2; }
  [ "$($ADB shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && break
  sleep 2
done
$ADB shell svc power stayon true >/dev/null 2>&1; $ADB shell input keyevent KEYCODE_WAKEUP; $ADB shell wm dismiss-keyguard
$ADB install -r "$E/pf/posterfox.apk" > "$R/install.txt" 2>&1 || { echo "INSTALL_FAILED"; cat "$R/install.txt"; exit 2; }
$ADB logcat -c
shot(){ $ADB exec-out screencap -p > "$R/$1.png"; }
# Tap the node whose text or content-desc matches (python reads the uiautomator dump); $2 = which match (last|first).
tap(){
  for _ in $(seq 1 15); do
    $ADB shell uiautomator dump /sdcard/u.xml >/dev/null 2>&1; $ADB pull -q /sdcard/u.xml "$R/u.xml" >/dev/null 2>&1
    xy=$(python3 - "$R/u.xml" "$1" "${2:-first}" <<'PY'
import re, sys, xml.etree.ElementTree as ET
want = re.compile(sys.argv[2], re.I); hits = []
for n in ET.parse(sys.argv[1]).iter("node"):
    label = (n.get("text") or "") + "|" + (n.get("content-desc") or "") + "|" + (n.get("hint") or "")
    if want.search(label):
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", n.get("bounds")))
        if x2 > x1 and y2 > y1: hits.append(((x1 + x2) // 2, (y1 + y2) // 2))
if hits: print(*(hits[-1] if sys.argv[3] == "last" else hits[0]))
PY
)
    [ -n "$xy" ] && { $ADB shell input tap $xy; return 0; }
    sleep 2
  done
  echo "NOT_FOUND $1"; return 1
}
$ADB shell monkey -p place.poster.posterfox -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 90; shot 01-started
# ---- pair: menu -> Extensions -> PosterChan Passwords -> Pair tab -> paste -> Pair ----
$ADB shell input keyevent KEYCODE_MENU; sleep 3
tap '^Extensions' && sleep 3 && tap 'PosterChan Passwords' && sleep 8; shot 02-popup
tap '^Pair$' first; sleep 2
tap 'paste the pairing code'; sleep 1
$ADB shell input text "$(cat "$RT/code.txt")"; sleep 1; shot 03-code
tap '^Pair$' last; sleep 25; shot 04-paired
# ---- desktop -> phone: the seeded bookmark must now be in the app's storage ----
grep -q "bridge addItem ok" <($ADB logcat -d) && echo "SEED_ADDED ok" || echo "SEED_ADDED missing"
# ---- phone -> desktop: bookmark a page in the app ----
$ADB shell am start -a android.intent.action.VIEW -d "https://example.org/made-on-the-phone" place.poster.posterfox >/dev/null; sleep 15
$ADB shell input keyevent KEYCODE_MENU; sleep 3
tap '^Bookmark' && sleep 3; shot 05-bookmarked
sleep 45                                  # the stand-in's poll (30 s) + the engine's publish debounce
$ADB logcat -d > "$R/logcat.txt"
cp "$RT/received.jsonl" "$R/received.jsonl"
grep -E "posterfox-bookmarks|FATAL" "$R/logcat.txt" | tail -20
REMOTE
scp -q "$OUT/run.sh" "$NAS:android-sdk-emu/pf/rt/run.sh" || exit 2
ssh "$NAS" 'bash ~/android-sdk-emu/pf/rt/run.sh </dev/null' > "$OUT/run.txt" 2>&1
scp -q "$NAS:android-sdk-emu/pf/rt/results/*" "$OUT/" 2>/dev/null
cat "$OUT/run.txt"
echo "--- what the phone published (opened with the vault key):"
node "$HERE/roundtrip_fixture.mjs" check "$EXT" "$OUT/fx" "$OUT/received.jsonl" | tee "$OUT/published.txt"
echo "results: $OUT"
ok=0
grep -q "SEED_ADDED ok" "$OUT/run.txt" && echo "PASS desktop -> phone" || { echo "FAIL desktop -> phone"; ok=1; }
grep -q '"url":"https://example.org/made-on-the-phone"' "$OUT/published.txt" && echo "PASS phone -> desktop" \
  || { echo "FAIL phone -> desktop"; ok=1; }
exit $ok

#!/usr/bin/env bash
# Install and start a PosterFox APK on the nas.lan emulator (the PosterChan repo's scripts/emulator_tests_on_nas.sh
# setup: ~/android-sdk-emu, AVD pc34 = API 34 x86_64, which runs this arm64 APK through Android's ARM translation).
# Same discipline as that script: one run at a time (its lock), nice/ionice, a hard timeout, and the emulator ALWAYS
# killed. Results in /tmp/pf-emu/<stamp>/ on this machine: smoke.txt, logcat.txt, screen.png.
#
#   tools/emulator_smoke.sh path/to/posterfox.apk        exit 0 = it started and stayed up; 1 = it crashed; 2 = could not run
set -uo pipefail
APK=${1:?usage: emulator_smoke.sh posterfox.apk}
NAS=${PC_EMU_HOST:-nas.lan}
OUT=/tmp/pf-emu/$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
LOCK=android-sdk-emu/run.lock
until ssh "$NAS" "mkdir ~/$LOCK 2>/dev/null && echo '$(hostname) pid=$$ posterfox-smoke since=$(date +%s)' > ~/$LOCK/owner"; do
  echo "emulator busy: $(ssh "$NAS" "cat ~/$LOCK/owner" 2>/dev/null) -- waiting"; sleep 20
done
trap 'ssh "$NAS" "rm -rf ~/$LOCK" 2>/dev/null' EXIT
ssh "$NAS" 'mkdir -p ~/android-sdk-emu/pf' && scp -q "$APK" "$NAS:android-sdk-emu/pf/posterfox.apk" || exit 2
# The remote half goes up as a FILE: run as `bash -s` from a heredoc, the emulator (and adb shell) read stdin -- the
# rest of the script -- and swallowed it, so nothing after the boot ran.
cat > "$OUT/run.sh" <<'REMOTE'
set -uo pipefail
E=$HOME/android-sdk-emu
export HOME=$E/home ANDROID_HOME=$E/sdk ANDROID_SDK_ROOT=$E/sdk ANDROID_USER_HOME=$E/user ANDROID_AVD_HOME=$E/avd
export ANDROID_ADB_SERVER_PORT=5137
PORT=5580; ADB="$ANDROID_HOME/platform-tools/adb -s emulator-$PORT"; R=$E/pf/results; rm -rf "$R"; mkdir -p "$R"
EMU_PID=
cleanup() {
  trap - EXIT INT TERM HUP
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
nice -n 19 ionice -c3 timeout --kill-after=30s 25m "$ANDROID_HOME/emulator/emulator" -avd pc34 \
  -port $PORT -no-window -no-audio -no-boot-anim -no-snapshot -wipe-data -no-snapshot-save \
  -gpu swangle -camera-back none -memory 3072 -cores 4 > "$R/emulator-console.txt" 2>&1 &
EMU_PID=$!
"$ANDROID_HOME/platform-tools/adb" start-server >/dev/null 2>&1
booted=
for _ in $(seq 1 300); do
  kill -0 "$EMU_PID" 2>/dev/null || { echo "EMULATOR_DIED"; exit 2; }
  [ "$($ADB shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ] && { booted=1; break; }
  sleep 2
done
[ -n "$booted" ] || { echo "BOOT_TIMEOUT"; exit 2; }
$ADB shell svc power stayon true >/dev/null 2>&1; $ADB shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
$ADB shell wm dismiss-keyguard >/dev/null 2>&1
$ADB install -r "$E/pf/posterfox.apk" > "$R/install.txt" 2>&1 || { echo "INSTALL_FAILED"; cat "$R/install.txt"; exit 2; }
echo "INSTALLED $($ADB shell dumpsys package place.poster.posterfox | grep -m1 versionName | tr -d '\r ')"
$ADB logcat -c
$ADB shell monkey -p place.poster.posterfox -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 120
pid=$($ADB shell pidof place.poster.posterfox | tr -d '\r')
echo "PID ${pid:-none}"
$ADB exec-out screencap -p > "$R/screen.png"
$ADB logcat -d > "$R/logcat.txt"
grep -E "FATAL EXCEPTION|AndroidRuntime: (FATAL|Process: place.poster)" -A12 "$R/logcat.txt" | head -60 > "$R/crash.txt"
echo "CRASH_LINES $(wc -l < "$R/crash.txt")"
grep -iE "posterfox-bookmarks|passwords@poster.place|PosterChan extension|privacy-badger|ublock" "$R/logcat.txt" | head -20
[ -n "$pid" ] && [ ! -s "$R/crash.txt" ]
REMOTE
scp -q "$OUT/run.sh" "$NAS:android-sdk-emu/pf/run.sh" || exit 2
ssh "$NAS" 'bash ~/android-sdk-emu/pf/run.sh </dev/null' > "$OUT/smoke.txt" 2>&1
rc=$?
scp -q "$NAS:android-sdk-emu/pf/results/logcat.txt" "$NAS:android-sdk-emu/pf/results/screen.png" "$NAS:android-sdk-emu/pf/results/crash.txt" "$OUT/" 2>/dev/null
cat "$OUT/smoke.txt"; echo "results: $OUT"
grep -q "EMULATOR_STOPPED" "$OUT/smoke.txt" || echo "WARNING: no EMULATOR_STOPPED line -- check nas for a leftover qemu"
exit $(( rc == 0 ? 0 : (rc == 2 ? 2 : 1) ))

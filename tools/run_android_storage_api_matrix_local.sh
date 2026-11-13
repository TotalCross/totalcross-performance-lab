#!/usr/bin/env bash
# Re-run the exact SDK 7.3.0 Android SQLite APK on a *local Apple Silicon Mac*.
# GitHub macOS hosted runners do not expose HVF; emulators must run on a
# physical host with virtualization, or an appropriately configured runner.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/build-tools/36.0.0:$PATH"
OUT_ROOT="${OUT_ROOT:-$ROOT/android-api-results}"
mkdir -p "$OUT_ROOT"

if [[ "$(uname -s)/$(uname -m)" != "Darwin/arm64" ]]; then
  echo "Requires a physical Apple Silicon Mac (Darwin/arm64) with HVF." >&2
  exit 2
fi
for command in gh sdkmanager avdmanager emulator adb python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing $command; install Android Studio SDK Command-line Tools and GitHub CLI." >&2
    exit 2
  fi
done
gh auth status >/dev/null

ARTIFACT=14007058527
PACKAGE="sqlite-plaintext-7.3.0-android-emulator"
ARCHIVE="$OUT_ROOT/official-android15-emulator-artifact.zip"
if [[ ! -f "$ARCHIVE" ]]; then
  gh api "repos/TotalCross/totalcross-performance-lab/actions/artifacts/$ARTIFACT/zip" > "$ARCHIVE"
fi
gh api "repos/TotalCross/totalcross-performance-lab/actions/artifacts/$ARTIFACT" \
  --jq '{id,name,digest,expired,size_in_bytes}' > "$OUT_ROOT/source-artifact.json"
python3 - "$ARCHIVE" "$OUT_ROOT/source-artifact.json" <<'PY'
import hashlib, json, pathlib, sys, zipfile
archive, meta = pathlib.Path(sys.argv[1]),json.loads(pathlib.Path(sys.argv[2]).read_text())
assert meta['id'] == 14007058527 and meta['name'] == 'sqlite-plaintext-7.3.0-android-emulator'
assert not meta['expired']
actual='sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()
assert actual==meta['digest'], (actual, meta['digest'])
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
print('Verified original 7.3.0 artifact:',actual)
PY

# The Python matrix runner uses adb commands without -s, so bind it to a
# dedicated, nonstandard emulator port. Do not touch existing AVD sessions.
export ANDROID_SERIAL=emulator-5562
CURRENT_AVD_PID=""
cleanup() {
  if [[ -n "$CURRENT_AVD_PID" ]]; then
    adb -s "$ANDROID_SERIAL" emu kill >/dev/null 2>&1 || true
    wait "$CURRENT_AVD_PID" 2>/dev/null || true
    CURRENT_AVD_PID=""
  fi
}
trap cleanup EXIT INT TERM

if [[ "$#" -eq 0 ]]; then
  set -- 24 29 35
fi
for api in "$@"; do
  case "$api" in 24|29|35) ;; *) echo "Invalid API: $api" >&2; exit 2 ;; esac
  echo "=== Android API $api / ARM64 ==="
  image="system-images;android-$api;google_apis;arm64-v8a"
  sdkmanager --install "platform-tools" "emulator" "build-tools;36.0.0" \
    "platforms;android-$api" "$image"
  avd="tc-storage-api-$api"
  if ! emulator -list-avds | grep -Fxq "$avd"; then
    echo "no" | avdmanager create avd -n "$avd" -k "$image" --device pixel_5
  fi
  out="$OUT_ROOT/api-$api"
  mkdir -p "$out"
  unzip -qo "$ARCHIVE" 'deployed/install/android/*' -d "$out"
  emulator -avd "$avd" -port 5562 -no-snapshot-load -no-snapshot-save \
    -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim \
    > "$out/emulator-console.log" 2>&1 &
  CURRENT_AVD_PID=$!
  adb -s "$ANDROID_SERIAL" wait-for-device
  booted=0
  for i in $(seq 1 180); do
    if [[ "$(adb -s "$ANDROID_SERIAL" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]]; then
      booted=1
      break
    fi
    sleep 5
  done
  if [[ "$booted" != 1 ]]; then
    echo "Emulator did not complete boot for API $api; inspect $out/emulator-console.log" >&2
    exit 1
  fi
  python3 "$SCRIPT_DIR/android_storage_api_matrix.py" --api-level "$api" --out "$out" --timeout 70
  cat "$out/android-api-matrix-summary.json"
  cleanup
done
echo "Completed API matrix. Evidence: $OUT_ROOT"

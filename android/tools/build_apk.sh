#!/usr/bin/env bash
# =============================================================================
# TITAN OMEGA INFINITY V18 — Android APK build
#
# Two paths are supported:
#
#  1) GRADLE PATH (portable): `android/gradlew assembleDebug` on any host that
#     can reach Maven Central + Google Maven. The Gradle project definition is
#     in android/app/build.gradle.kts.
#
#  2) SELF-CONTAINED PATH (this sandbox): aapt2 + kotlinc + d8 + apk_sign_ts,
#     using only toolchain components fetched from allowlisted hosts.
#     See scripts/toolchain/setup_toolchain.sh.
#
# Usage:  android/tools/build_apk.sh [--release] [--out DIR]
# =============================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ANDROID_DIR="$(cd "$HERE/.." && pwd)"
REPO_ROOT="$(cd "$ANDROID_DIR/.." && pwd)"
TOOLCHAIN="${TITAN_TOOLCHAIN_DIR:-/opt/titan/toolchain}"

VARIANT="debug"
OUT_DIR="$ANDROID_DIR/build/outputs/apk"
while [ $# -gt 0 ]; do
  case "$1" in
    --release) VARIANT="release"; shift;;
    --out) OUT_DIR="$2"; shift 2;;
    *) echo "unknown argument: $1"; exit 2;;
  esac
done

AAPT2="$TOOLCHAIN/build-tools/aapt2"
JAVA="$TOOLCHAIN/jdk/bin/java"
KOTLINC="$TOOLCHAIN/kotlinc/bin/kotlinc"
D8_JAR="$TOOLCHAIN/d8/d8.jar"
ANDROID_JAR="$TOOLCHAIN/platforms/android-35/android.jar"
KOTLIN_STDLIB="$TOOLCHAIN/kotlinc/lib/kotlin-stdlib.jar"

for tool in "$AAPT2" "$JAVA" "$KOTLINC" "$D8_JAR" "$ANDROID_JAR"; do
  if [ ! -e "$tool" ]; then
    echo "BLOCKER: required toolchain component missing: $tool"
    echo "Run scripts/toolchain/setup_toolchain.sh first."
    exit 3
  fi
done

SRC="$ANDROID_DIR/app/src/main/java"
RES="$ANDROID_DIR/app/src/main/res"
MANIFEST="$ANDROID_DIR/app/src/main/AndroidManifest.xml"
BUILD="$ANDROID_DIR/build/manual"
rm -rf "$BUILD"
mkdir -p "$BUILD/compiled" "$BUILD/dex" "$BUILD/gen" "$BUILD/classes" "$OUT_DIR"

echo "== 1/6  aapt2 compile resources"
"$AAPT2" compile --dir "$RES" -o "$BUILD/compiled/res.zip" || exit 4

echo "== 2/6  aapt2 link (resources + manifest)"
"$AAPT2" link \
  -o "$BUILD/base.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$MANIFEST" \
  --min-sdk-version 24 \
  --target-sdk-version 35 \
  --version-code 18 \
  --version-name "18.0.0" \
  "$BUILD/compiled/res.zip" || exit 5

echo "== 3/6  kotlinc -> classes"
SOURCES=$(find "$SRC" -name '*.kt' | sort)
if [ -z "$SOURCES" ]; then echo "BLOCKER: no Kotlin sources found under $SRC"; exit 4; fi
"$KOTLINC" $SOURCES \
  -classpath "$ANDROID_JAR" \
  -jvm-target 1.8 \
  -nowarn \
  -d "$BUILD/classes" || exit 6

echo "== 4/6  d8 -> dex"
# D8 consumes jars/class files, not loose directories: pack first.
(cd "$BUILD/classes" && zip -q -r "$BUILD/app-classes.jar" .) || exit 7
"$JAVA" -cp "$D8_JAR" com.android.tools.r8.D8 \
  --lib "$ANDROID_JAR" \
  --min-api 24 \
  --release \
  --output "$BUILD/dex" \
  "$BUILD/app-classes.jar" \
  "$KOTLIN_STDLIB" || exit 7

echo "== 5/6  assemble unsigned APK"
cd "$BUILD"
cp base.apk unsigned.apk
for dex in dex/*.dex; do
  [ -e "$dex" ] || continue
  zip -q -j unsigned.apk "$dex" || exit 8
done

echo "== 6/6  sign APK (apksigner: JAR v1 + APK Signature Scheme v2/v3)"
KEYSTORE="$ANDROID_DIR/titan-release.jks"
KEY_ALIAS="titan"
KEY_PASS="${TITAN_KEY_PASSWORD:-titan-release-2026}"
if [ "$VARIANT" != "release" ]; then
  KEYSTORE="$ANDROID_DIR/titan-debug.jks"
  KEY_ALIAS="androiddebugkey"
  KEY_PASS="android"
fi
if [ ! -f "$KEYSTORE" ]; then
  echo "-- generating $VARIANT keystore"
  "$TOOLCHAIN/jdk/bin/keytool" -genkeypair -v \
    -keystore "$KEYSTORE" -alias "$KEY_ALIAS" \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass "$KEY_PASS" -keypass "$KEY_PASS" \
    -dname "CN=TITAN Omega Infinity, OU=TITAN, O=TITAN, L=Dhaka, C=BD" || exit 9
fi

"$JAVA" -cp "$TOOLCHAIN/build-tools/apksigner.jar" com.android.apksigner.ApkSignerTool sign \
  --ks "$KEYSTORE" \
  --ks-key-alias "$KEY_ALIAS" \
  --ks-pass "pass:$KEY_PASS" \
  --key-pass "pass:$KEY_PASS" \
  --v1-signing-enabled true \
  --v2-signing-enabled true \
  --v3-signing-enabled true \
  --min-sdk-version 24 \
  --out "$OUT_DIR/titan-omega-$VARIANT.apk" \
  "$BUILD/unsigned.apk" || exit 10

"$JAVA" -cp "$TOOLCHAIN/build-tools/apksigner.jar" com.android.apksigner.ApkSignerTool verify \
  --min-sdk-version 24 --print-certs "$OUT_DIR/titan-omega-$VARIANT.apk" || exit 11

FINAL="$OUT_DIR/titan-omega-$VARIANT.apk"
echo
echo "================================================================"
echo "APK BUILT: $FINAL"
echo "size:      $(stat -c%s "$FINAL") bytes"
echo "sha256:    $(sha256sum "$FINAL" | cut -d' ' -f1)"
echo "variant:   $VARIANT"
echo "version:   18.0.0 (versionCode 18)"
echo "================================================================"
"$AAPT2" dump badging "$FINAL" 2>/dev/null | head -6

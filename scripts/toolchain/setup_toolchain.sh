#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# TITAN OMEGA INFINITY V18 - offline Android/JVM toolchain bootstrap.
#
# The build host for this project has a strict TLS egress allowlist:
#   github.com, api.github.com, codeload.github.com,
#   registry.npmjs.org, pypi.org, files.pythonhosted.org
# Everything below is fetched from one of those hosts. Nothing here needs
# Gradle, Android Studio, the Android SDK manager or dl.google.com.
#
# Installed layout (default $TOOLCHAIN_DIR = /opt/titan/toolchain):
#
#   jdk/                     Temurin JRE 17 (from the jdk4py wheel)
#   build-tools/aapt2        Google aapt2 (from the aaptjs3 npm package)
#   build-tools/apksigner.jar Google apksigner (from @drxiaozhi/minapk)
#   d8/d8.jar                Google D8/R8 8.2.2 (from @drxiaozhi/minapk)
#   platforms/android-35/android.jar, android-34/android.jar
#   kotlinc/                 Kotlin 2.4.21 compiler (from the kotlin-compiler npm package)
#   apksigner/               apk_sign_ts@1.0.1 (fallback signer, JS)
#
# Usage:  bash scripts/toolchain/setup_toolchain.sh [--dir DIR]
# ---------------------------------------------------------------------------
set -euo pipefail

TOOLCHAIN_DIR="${TOOLCHAIN_DIR:-/opt/titan/toolchain}"
VENV_DIR="${VENV_DIR:-/opt/titan/venv}"
PY="${PYTHON:-python3}"

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) TOOLCHAIN_DIR="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$TOOLCHAIN_DIR"/{build-tools,d8,platforms,apksigner}
WORK="$(mktemp -d /tmp/titan-toolchain-XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

log() { printf '[toolchain] %s\n' "$*"; }

# --------------------------------------------------------------------------
# 1. JRE 17 (jdk4py wheel).  The wheel ships a full JDK-like tree at
#    <wheel>/java-runtime/ - it is NOT named "jdk*", which is what broke the
#    previous version of this script.
# --------------------------------------------------------------------------
if [ ! -x "$TOOLCHAIN_DIR/jdk/bin/java" ]; then
  log "fetching jdk4py (Temurin JRE 17)"
  "$PY" -m pip download --no-deps --dest "$WORK" "jdk4py==17.0.9.2" >/dev/null
  WHL="$(ls "$WORK"/jdk4py-*.whl | head -n1)"
  mkdir -p "$WORK/jdkx"
  "$PY" -m zipfile -e "$WHL" "$WORK/jdkx"
  # layout is java-runtime/ inside the wheel
  if [ -d "$WORK/jdkx/java-runtime" ]; then
    rm -rf "$TOOLCHAIN_DIR/jdk"
    mv "$WORK/jdkx/java-runtime" "$TOOLCHAIN_DIR/jdk"
  elif [ -d "$WORK/jdkx/jdk" ]; then
    rm -rf "$TOOLCHAIN_DIR/jdk"
    mv "$WORK/jdkx/jdk" "$TOOLCHAIN_DIR/jdk"
  else
    echo "!! could not locate the java-runtime directory inside $WHL" >&2
    exit 1
  fi
  chmod +x "$TOOLCHAIN_DIR/jdk/bin/"* 2>/dev/null || true
fi
log "java: $("$TOOLCHAIN_DIR/jdk/bin/java" -version 2>&1 | head -n1)"

# --------------------------------------------------------------------------
# 2. aapt2 (npm: aaptjs3 bundles the real Google aapt2 linux binary)
# --------------------------------------------------------------------------
if [ ! -x "$TOOLCHAIN_DIR/build-tools/aapt2" ]; then
  log "fetching aapt2 via npm (aaptjs3)"
  (cd "$WORK" && npm pack aaptjs3 >/dev/null 2>&1)
  mkdir -p "$WORK/aapt2x" && tar xzf "$WORK"/aaptjs3-*.tgz -C "$WORK/aapt2x"
  AAPT2="$(find "$WORK/aapt2x" -type f -name 'aapt2' | head -n1)"
  [ -n "$AAPT2" ] || { echo "!! aapt2 binary not found in aaptjs3" >&2; exit 1; }
  install -m 0755 "$AAPT2" "$TOOLCHAIN_DIR/build-tools/aapt2"
fi
log "aapt2: $("$TOOLCHAIN_DIR/build-tools/aapt2" version 2>&1 | head -n1)"

# --------------------------------------------------------------------------
# 3. D8 dexer + apksigner (npm: @drxiaozhi/minapk bundles both real jars).
#    NOTE: the npm package `d8-termux` is NOT usable here - its d8.jar is an
#    Android-native binary, not a Java archive.
# --------------------------------------------------------------------------
if [ ! -f "$TOOLCHAIN_DIR/d8/d8.jar" ] || [ ! -f "$TOOLCHAIN_DIR/build-tools/apksigner.jar" ]; then
  log "fetching D8 + apksigner via npm (@drxiaozhi/minapk)"
  (cd "$WORK" && npm pack @drxiaozhi/minapk >/dev/null 2>&1)
  mkdir -p "$WORK/minapk" && tar xzf "$WORK"/drxiaozhi-minapk-*.tgz -C "$WORK/minapk"
  [ -f "$WORK/minapk/package/tools/d8.jar" ] && install -m 0644 "$WORK/minapk/package/tools/d8.jar" "$TOOLCHAIN_DIR/d8/d8.jar"
  [ -f "$WORK/minapk/package/tools/apksigner.jar" ] && install -m 0644 "$WORK/minapk/package/tools/apksigner.jar" "$TOOLCHAIN_DIR/build-tools/apksigner.jar"
fi
log "d8: $("$TOOLCHAIN_DIR/jdk/bin/java" -cp "$TOOLCHAIN_DIR/d8/d8.jar" com.android.tools.r8.D8 --version 2>&1 | head -n1)"
log "apksigner: $("$TOOLCHAIN_DIR/jdk/bin/java" -cp "$TOOLCHAIN_DIR/build-tools/apksigner.jar" com.android.apksigner.ApkSignerTool version 2>&1 | head -n1)"

# --------------------------------------------------------------------------
# 4. android.jar platform stubs (github.com Sable/android-platforms is a plain
#    git mirror of the AOSP platform trees - no LFS, no release assets).
# --------------------------------------------------------------------------
if [ ! -f "$TOOLCHAIN_DIR/platforms/android-35/android.jar" ]; then
  log "fetching android.jar platform stubs (Sable/android-platforms)"
  (cd "$WORK" && curl -fsSL -o platforms.zip \
     "https://codeload.github.com/Sable/android-platforms/zip/refs/heads/master")
  mkdir -p "$WORK/plat" && "$PY" - <<'PYEOF'
import zipfile, os, shutil
z = zipfile.ZipFile(os.path.join(os.environ["WORK"], "platforms.zip"))
targets = {"android-35": "android.jar", "android-34": "android.jar"}
root = z.namelist()[0]
for api in targets:
    member = f"{root}android-{api}/android.jar"
    if member in z.namelist():
        dst = os.path.join(os.environ["TOOLCHAIN_DIR"], "platforms", api)
        os.makedirs(dst, exist_ok=True)
        with z.open(member) as src, open(os.path.join(dst, "android.jar"), "wb") as out:
            shutil.copyfileobj(src, out)
        print(f"installed platforms/{api}/android.jar")
PYEOF
fi

# --------------------------------------------------------------------------
# 5. Kotlin compiler (npm: kotlin-compiler)
# --------------------------------------------------------------------------
if [ ! -x "$TOOLCHAIN_DIR/kotlinc/bin/kotlinc" ]; then
  log "fetching Kotlin compiler via npm (kotlin-compiler)"
  (cd "$WORK" && npm pack kotlin-compiler >/dev/null 2>&1)
  mkdir -p "$WORK/kx" && tar xzf "$WORK"/kotlin-compiler-*.tgz -C "$WORK/kx"
  rm -rf "$TOOLCHAIN_DIR/kotlinc"
  mv "$WORK/kx/package" "$TOOLCHAIN_DIR/kotlinc"
fi
log "kotlinc: $("$TOOLCHAIN_DIR/jdk/bin/java" -cp "$TOOLCHAIN_DIR/kotlinc/lib/kotlin-compiler.jar" \
      org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -version 2>&1 | head -n1)"

# --------------------------------------------------------------------------
# 6. apk_sign_ts (fallback JS signer, used only if apksigner.jar is missing)
# --------------------------------------------------------------------------
if [ ! -d "$TOOLCHAIN_DIR/apksigner/node_modules/apk_sign_ts" ]; then
  log "fetching apk_sign_ts (fallback signer)"
  (cd "$TOOLCHAIN_DIR/apksigner" && npm install --silent apk_sign_ts@1.0.1 >/dev/null 2>&1) || true
fi

# --------------------------------------------------------------------------
# 7. Python backend virtualenv
# --------------------------------------------------------------------------
if [ ! -x "$VENV_DIR/bin/python" ]; then
  log "creating backend venv at $VENV_DIR"
  "$PY" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
fi
log "installing backend requirements"
"$VENV_DIR/bin/pip" install --quiet -r "$(dirname "$0")/../../backend/requirements.txt"

echo
echo "SETUP_COMPLETE"
echo "  TOOLCHAIN_DIR=$TOOLCHAIN_DIR"
echo "  VENV_DIR=$VENV_DIR"
echo "  build:  JAVA_HOME=$TOOLCHAIN_DIR/jdk bash android/tools/build_apk.sh --release"

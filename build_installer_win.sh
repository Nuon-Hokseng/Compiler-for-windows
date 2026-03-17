#!/bin/bash
# ================================================================
#  build_installer_win.sh
#  Flow:
#    1. PyInstaller  -> backend/dist/backend.exe
#    2. Next.js      -> frontend/.next (compiled only)
#    3. NSIS         -> IGAutomation-Setup.exe
# ================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/_win_build"
OUTPUT="$SCRIPT_DIR/IGAutomation-Setup.exe"

echo "================================================"
echo "  IG Automation - Building Windows EXE"
echo "================================================"

# ── CHECKS ───────────────────────────────────────────
echo "Checking required files..."
for f in "frontend" "backend" "setup.ps1" "installer.nsi" "AppIcon.ico"; do
    [ ! -e "$SCRIPT_DIR/$f" ] && echo "[ERROR] $f not found in project root" && exit 1
done
for enc in "backend/.env.enc" "frontend/.env.enc"; do
    [ ! -f "$SCRIPT_DIR/$enc" ] && echo "[ERROR] $enc not found. Run: python create_env.py" && exit 1
done
if ! command -v makensis &>/dev/null; then
    echo "[ERROR] makensis not found"; exit 1
fi
echo "[OK] All checks passed."

npm install -g terser 2>/dev/null || true

# ── STEP 1: COMPILE BACKEND ──────────────────────────
echo ""
echo "================================================"
echo "  Step 1/3: Compiling backend with PyInstaller"
echo "================================================"

cd "$SCRIPT_DIR/backend"
pip install pyinstaller --quiet
pip install -r requirements.txt --quiet

python3 << 'PYEOF'
import os, sys, subprocess

local_packages = []
local_datas = [(".env.enc", ".")]
for item in os.listdir("."):
    if os.path.isdir(item) and os.path.exists(os.path.join(item, "__init__.py")):
        if item not in ["dist", "build_tmp", "__pycache__", "venv"]:
            local_packages.append(item)
            local_datas.append((item, item))

# Bundle playwright package files
try:
    result = subprocess.run([sys.executable, "-c",
        "import playwright, os; print(os.path.dirname(playwright.__file__))"],
        capture_output=True, text=True)
    pw_path = result.stdout.strip()
    if pw_path and os.path.exists(pw_path):
        local_datas.append((pw_path, "playwright"))
        print(f"[OK] Playwright bundled from: {pw_path}")
except Exception as e:
    print(f"[WARN] Could not bundle playwright: {e}")

print(f"[OK] Local packages: {local_packages}")

hidden = local_packages + [
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "fastapi", "fastapi.middleware", "fastapi.middleware.cors",
    "fastapi.middleware.gzip", "fastapi.middleware.trustedhost",
    "fastapi.responses", "fastapi.routing", "fastapi.staticfiles",
    "fastapi.security", "fastapi.background", "fastapi.encoders",
    "starlette", "starlette.routing", "starlette.requests", "starlette.responses",
    "starlette.middleware", "starlette.middleware.cors", "starlette.middleware.base",
    "starlette.middleware.gzip", "starlette.middleware.trustedhost",
    "starlette.staticfiles", "starlette.background", "starlette.concurrency",
    "starlette.datastructures", "starlette.exceptions", "starlette.types",
    "starlette.websockets", "starlette.formparsers",
    "pydantic", "pydantic.v1",
    "pydantic.deprecated.class_validators", "pydantic.deprecated.config",
    "pydantic.deprecated.tools",
    "anyio", "anyio.from_thread", "anyio.abc",
    "anyio.streams.memory", "anyio.streams.stapled", "anyio.streams.tls",
    "playwright", "playwright.sync_api", "playwright.async_api",
    "playwright._impl._api_types", "playwright._impl._browser",
    "playwright._impl._browser_context", "playwright._impl._browser_type",
    "playwright._impl._connection", "playwright._impl._transport",
    "playwright._impl._driver", "playwright._impl._element_handle",
    "playwright._impl._errors", "playwright._impl._frame",
    "playwright._impl._helper", "playwright._impl._input",
    "playwright._impl._js_handle", "playwright._impl._keyboard",
    "playwright._impl._locator", "playwright._impl._mouse",
    "playwright._impl._network", "playwright._impl._page",
    "playwright._impl._playwright", "playwright._impl._sync_base",
    "playwright._impl._async_base",
    "dotenv", "cryptography",
    "langchain", "langchain_core", "langchain_community",
    "langchain_openai", "langchain_anthropic", "langchain_ollama",
    "supabase", "multipart", "httpx", "httpcore",
    "email_validator", "jose", "passlib",
]

lines = [
    "# -*- mode: python ; coding: utf-8 -*-",
    "a = Analysis(",
    '    ["run.py"],',
    '    pathex=["."],',
    "    binaries=[],",
    "    datas=" + repr(local_datas) + ",",
    "    hiddenimports=" + repr(hidden) + ",",
    "    hookspath=[],",
    "    hooksconfig={},",
    "    runtime_hooks=[],",
    "    excludes=[",
    '        "tkinter", "unittest", "test",',
    '        "pydoc", "doctest", "difflib",',
    "    ],",
    "    noarchive=False,",
    ")",
    "pyz = PYZ(a.pure)",
    "exe = EXE(",
    "    pyz, a.scripts, a.binaries, a.datas, [],",
    '    name="backend",',
    "    debug=False,",
    "    bootloader_ignore_signals=False,",
    "    strip=False,",
    "    upx=True,",
    "    upx_exclude=[],",
    "    runtime_tmpdir=None,",
    "    console=True,",
    "    disable_windowed_traceback=False,",
    "    argv_emulation=False,",
    "    target_arch=None,",
    "    codesign_identity=None,",
    "    entitlements_file=None,",
    ")",
]

with open("backend.spec", "w") as f:
    f.write("\n".join(lines))
print("[OK] backend.spec written")
PYEOF

pyinstaller backend.spec --distpath dist --workpath build_tmp --noconfirm --clean
rm -rf build_tmp backend.spec __pycache__

[ ! -f "dist/backend.exe" ] && echo "[ERROR] PyInstaller failed" && exit 1
echo "[OK] backend.exe: $(du -sh dist/backend.exe | cut -f1)"

cd "$SCRIPT_DIR"

# ── STEP 2: BUILD FRONTEND ───────────────────────────
echo ""
echo "================================================"
echo "  Step 2/3: Building frontend"
echo "================================================"

cd "$SCRIPT_DIR/frontend"

# Clean prebuild scripts
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
let changed = false;
for (const key of ['prebuild','preinstall','predeploy','predev','prestart']) {
    if (pkg.scripts && pkg.scripts[key]) { delete pkg.scripts[key]; changed = true; }
}
for (const [key, val] of Object.entries(pkg.scripts || {})) {
    if (val.includes('decrypt-env')) { delete pkg.scripts[key]; changed = true; }
}
if (changed) fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
console.log('[OK] package.json cleaned');
"

# Write load-env.js
cat > load-env.js << 'JSEOF'
const fs     = require('fs');
const path   = require('path');
const crypto = require('crypto');
const SECRET_KEY = '9cbfcce635d1160bf8fd4143a322ef1c1edebc84749ae1d34bcb167347754406';
const ENC_PATH   = path.join(__dirname, '.env.enc');
function loadEnv() {
    if (!fs.existsSync(ENC_PATH)) { console.error('[load-env] .env.enc not found'); return; }
    const enc    = Buffer.from(fs.readFileSync(ENC_PATH).toString().trim(), 'base64');
    const keyBuf = crypto.createHash('sha256').update(SECRET_KEY).digest();
    const plain  = Buffer.alloc(enc.length);
    for (let i = 0; i < enc.length; i++) plain[i] = enc[i] ^ keyBuf[i % keyBuf.length];
    let loaded = 0;
    for (const line of plain.toString('utf8').split('\n')) {
        const t = line.trim();
        if (!t || t.startsWith('#') || !t.includes('=')) continue;
        const [k, ...rest] = t.split('=');
        const key = k.trim();
        const val = rest.join('=').trim().replace(/^["']|["']$/g, '');
        if (key && !(key in process.env)) { process.env[key] = val; loaded++; }
    }
    console.log('[load-env] ' + loaded + ' vars loaded');
}
loadEnv();
module.exports = {};
JSEOF

# Patch next.config.js
if [ -f "next.config.js" ]; then
    if ! grep -q "load-env" next.config.js; then
        echo "require('./load-env');" | cat - next.config.js > /tmp/nc.js && mv /tmp/nc.js next.config.js
    fi
else
    printf "require('./load-env');\n/** @type {import('next').NextConfig} */\nconst nextConfig = {};\nmodule.exports = nextConfig;\n" > next.config.js
fi

# Install ALL deps (including dev) for build — tailwind/postcss are devDeps
npm install --silent

# Production build
npm run build
[ $? -ne 0 ] && echo "[ERROR] Frontend build failed" && exit 1

# ── SLIM DOWN node_modules ───────────────────────────
echo "Slimming node_modules..."

# Prune dev deps AFTER build is complete
npm prune --omit=dev --silent 2>/dev/null || true

# Remove known large unnecessary files/folders using Python (cross-platform safe)
python3 << 'TRIMEOF'
import os, shutil, pathlib

base = pathlib.Path("node_modules")
remove_dirs  = {".cache","test","tests","__tests__","docs","examples","coverage","fixtures"}
remove_exts  = {".map"}
remove_names = {"LICENSE","LICENSE.md","LICENSE.txt","CHANGELOG.md","CHANGELOG.txt",
                "HISTORY.md","AUTHORS","AUTHORS.md","README.md","readme.md"}

removed = 0
for root, dirs, files in os.walk(base, topdown=True):
    # Remove dirs in-place to prevent os.walk from descending into them
    dirs[:] = [d for d in dirs if d not in remove_dirs]
    for d in list(dirs):
        full = pathlib.Path(root) / d
        if d in remove_dirs:
            shutil.rmtree(full, ignore_errors=True)
            removed += 1
    for f in files:
        fp = pathlib.Path(root) / f
        if fp.suffix in remove_exts or fp.name in remove_names:
            try: fp.unlink(); removed += 1
            except: pass
        # Remove .ts but keep .d.ts
        elif fp.suffix == ".ts" and not f.endswith(".d.ts"):
            try: fp.unlink(); removed += 1
            except: pass

print(f"[OK] Removed {removed} unnecessary files/dirs from node_modules")
TRIMEOF

echo "[OK] node_modules slimmed: $(du -sh node_modules | cut -f1)"

# Strip source files — ship only compiled output
echo "Stripping source files..."
find . -maxdepth 1 -name "*.ts"  -delete
find . -maxdepth 1 -name "*.tsx" -delete
find . -maxdepth 1 -name "*.mjs" -delete
rm -rf src app pages components lib hooks utils styles
rm -f load-env.js decrypt-env.mjs
echo "[OK] Source stripped."

cd "$SCRIPT_DIR"

# ── DOWNLOAD CHROMIUM AT BUILD TIME ──────────────────
echo "Downloading Chromium (bundling into installer)..."
mkdir -p "$BUILD_DIR/payload/browsers"
export PLAYWRIGHT_BROWSERS_PATH="$BUILD_DIR/payload/browsers"
python3 -m playwright install chromium
if [ $? -eq 0 ]; then
    echo "[OK] Chromium bundled: $(du -sh "$BUILD_DIR/payload/browsers" | cut -f1)"
else
    echo "[WARN] Chromium download failed — client will download on first use."
fi

# ── STEP 3: PACKAGE WITH NSIS ────────────────────────
echo ""
echo "================================================"
echo "  Step 3/3: Packaging installer"
echo "================================================"

rm -rf "$BUILD_DIR/payload/backend" "$BUILD_DIR/payload/frontend"
mkdir -p "$BUILD_DIR/payload/backend"
mkdir -p "$BUILD_DIR/payload/frontend"

# Backend: exe + .env.enc only
cp "$SCRIPT_DIR/backend/dist/backend.exe" "$BUILD_DIR/payload/backend/backend.exe"
cp "$SCRIPT_DIR/backend/.env.enc"         "$BUILD_DIR/payload/backend/.env.enc"
echo "[OK] Backend: $(du -sh "$BUILD_DIR/payload/backend" | cut -f1)"

# Frontend: .next + slimmed node_modules + config files
cp -r "$SCRIPT_DIR/frontend/.next"          "$BUILD_DIR/payload/frontend/.next"
cp -r "$SCRIPT_DIR/frontend/node_modules"   "$BUILD_DIR/payload/frontend/node_modules"
cp    "$SCRIPT_DIR/frontend/package.json"   "$BUILD_DIR/payload/frontend/package.json"
cp    "$SCRIPT_DIR/frontend/.env.enc"       "$BUILD_DIR/payload/frontend/.env.enc"
[ -f "$SCRIPT_DIR/frontend/next.config.js" ] &&     cp "$SCRIPT_DIR/frontend/next.config.js" "$BUILD_DIR/payload/frontend/next.config.js"
[ -f "$SCRIPT_DIR/frontend/next.config.ts" ] &&     cp "$SCRIPT_DIR/frontend/next.config.ts" "$BUILD_DIR/payload/frontend/next.config.ts"
echo "[OK] Frontend: $(du -sh "$BUILD_DIR/payload/frontend" | cut -f1)"

cp "$SCRIPT_DIR/setup.ps1"     "$BUILD_DIR/setup.ps1"
cp "$SCRIPT_DIR/installer.nsi" "$BUILD_DIR/installer.nsi"
cp "$SCRIPT_DIR/AppIcon.ico"   "$BUILD_DIR/AppIcon.ico"

echo "Total payload: $(du -sh "$BUILD_DIR/payload" | cut -f1)"
echo "Compiling NSIS installer (LZMA compression)..."
cd "$BUILD_DIR"
makensis installer.nsi

mv "$BUILD_DIR/IGAutomation-Setup.exe" "$OUTPUT"
rm -rf "$BUILD_DIR"

echo ""
echo "================================================"
echo "  DONE: $OUTPUT"
echo "  Size: $(du -sh "$OUTPUT" | cut -f1)"
echo "================================================"

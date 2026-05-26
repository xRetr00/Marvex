#!powershell
<#
.SYNOPSIS
    Build Marvex Windows installer (NSIS/MSI) from source.
    
.DESCRIPTION
    Comprehensive build script that:
    1. Validates environment (Node, Cargo, Rust, uv, Python 3.12+)
    2. Builds Python wheel (marvex-*.whl, staged with its valid wheel filename)
    3. Prepares runtime resources (uv.exe bundling)
    4. Builds React/Vite frontend
    5. Builds Tauri app + generates NSIS/MSI installers (unless -SkipInstaller)
    
    This script implements Tier 1 (Production) packaging:
    - Console scripts from setuptools (not frozen PyInstaller)
    - Dynamic Python runtime in ~/.marvex/runtime/venv/
    - Supports runtime package installation
    
.EXAMPLE
    .\build-installer.ps1
    
.EXAMPLE
    .\build-installer.ps1 -SkipValidation -Clean
    
.EXAMPLE
    .\build-installer.ps1 -Verbose

.EXAMPLE
    .\build-installer.ps1 -SkipInstaller
    # Build everything except the final installer (faster for development)
#>

param(
    [switch]$SkipValidation,
    [switch]$Clean,
    [switch]$Verbose,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$ShellDir = Join-Path $RepoRoot "apps\shell"
$ShellSrcDir = Join-Path $ShellDir "src"
$ShellTauriDir = Join-Path $ShellDir "src-tauri"
$ControlPlaneDir = Join-Path $RepoRoot "apps\control_plane_web"
$RuntimeDir = Join-Path $ShellDir "runtime"
$DistDir = Join-Path $ShellDir "dist"

# ============================================================================
# Load Version from Central File
# ============================================================================

$VersionFile = Join-Path $RepoRoot "version.toml"
if (-not (Test-Path $VersionFile)) {
    Write-Host "✗ ERROR: version.toml not found at $VersionFile" -ForegroundColor Red
    exit 1
}

$versionContent = Get-Content -LiteralPath $VersionFile
$versionLine = $versionContent | Where-Object { $_ -match '^\s*version\s*=' } | Select-Object -First 1
if (-not $versionLine -or $versionLine -notmatch 'version\s*=\s*"([^"]+)"') {
    Write-Host "✗ ERROR: Could not parse version from $VersionFile" -ForegroundColor Red
    exit 1
}
$AppVersion = $matches[1]

# ============================================================================
# Logging helpers
# ============================================================================

function Write-Section {
    param([string]$Message)
    Write-Host ""
    Write-Host "┌──────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
    Write-Host "│ $($Message.PadRight(56)) │" -ForegroundColor Cyan
    Write-Host "└──────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message, [int]$Step, [int]$Total)
    Write-Host "[$Step/$Total] $Message" -ForegroundColor Green
}

function Write-Error-Exit {
    param([string]$Message)
    Write-Host "✗ ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Invoke-NpmCi {
    param([string]$Label)

    $npmOutput = & npm ci 2>&1
    $npmExitCode = $LASTEXITCODE
    $npmOutput | Where-Object { $_ -match 'added|up to date|audited|found 0 vulnerabilities' } | ForEach-Object {
        Write-Host $_
    }

    if ($npmExitCode -ne 0) {
        $npmOutput | Select-Object -Last 20 | ForEach-Object {
            Write-Host $_ -ForegroundColor DarkYellow
        }
        Write-Error-Exit "npm ci failed for $Label. Close running Node/Vite dev servers that may lock node_modules native packages, then retry."
    }
}

# ============================================================================
# Validation
# ============================================================================

function Validate-Environment {
    if ($SkipValidation) {
        Write-Host "⚠ Skipping environment validation" -ForegroundColor Yellow
        return
    }
    
    Write-Section "Validating Environment"
    
    # Check Node.js
    $nodeVersion = node --version 2>$null
    if (-not $nodeVersion) {
        Write-Error-Exit "Node.js not found. Install from https://nodejs.org/"
    }
    Write-Success "Node.js: $nodeVersion"
    
    # Check npm
    $npmVersion = npm --version 2>$null
    if (-not $npmVersion) {
        Write-Error-Exit "npm not found"
    }
    Write-Success "npm: $npmVersion"
    
    # Check Rust/Cargo
    $cargoVersion = cargo --version 2>$null
    if (-not $cargoVersion) {
        Write-Error-Exit "Cargo not found. Install from https://rustup.rs/"
    }
    Write-Success "Cargo: $cargoVersion"
    
    # Check uv
    $uvVersion = uv --version 2>$null
    if (-not $uvVersion) {
        Write-Error-Exit "uv not found. Install with: pip install uv"
    }
    Write-Success "uv: $uvVersion"
    
    # Check Python 3.12+
    $pythonVersion = python --version 2>$null
    if (-not $pythonVersion) {
        Write-Error-Exit "Python not found. Install Python 3.12+ from https://www.python.org/"
    }
    Write-Success "Python: $pythonVersion"
    
    # Verify Python is 3.12+
    $pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ([version]$pyVer -lt [version]"3.12") {
        Write-Error-Exit "Python 3.12 or higher required. Found: $pyVer"
    }
    
    Write-Success "Marvex App Version: $AppVersion"
    
    Write-Host ""
}

# ============================================================================
# Clean
# ============================================================================

function Clean-Previous-Build {
    if (-not $Clean) {
        return
    }
    
    Write-Section "Cleaning Previous Build"
    
    @(
        (Join-Path $ShellDir "dist"),
        (Join-Path $ShellDir "build"),
        (Join-Path $ShellDir "node_modules"),
        (Join-Path $ShellTauriDir "target"),
        (Join-Path $ControlPlaneDir "dist"),
        (Join-Path $ControlPlaneDir "node_modules")
    ) | ForEach-Object {
        if (Test-Path $_) {
            Write-Host "Removing: $_" -ForegroundColor Gray
            Remove-Item -Path $_ -Recurse -Force
        }
    }
    
    Write-Success "Previous build cleaned"
    Write-Host ""
}

# ============================================================================
# Step 1: Build Python Wheel
# ============================================================================

function Build-Python-Wheel {
    Write-Section "Step 1: Building Python Wheel"
    
    Push-Location $RepoRoot
    try {
        Write-Step "Building marvex wheel..." 1 5
        
        # Build wheel using uv
        $output = uv build --wheel 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Exit "Failed to build Python wheel: $output"
        }
        
        # Find the generated wheel
        $wheel = Get-ChildItem -Path (Join-Path $RepoRoot "dist") -Filter "marvex-*.whl" | 
                 Sort-Object LastWriteTime -Descending | 
                 Select-Object -First 1
        
        if (-not $wheel) {
            Write-Error-Exit "Wheel build succeeded but no .whl file found in dist/"
        }
        
        Write-Success "Wheel built: $($wheel.Name)"
        
        # Verify wheel has console scripts
        Write-Host "  Verifying console scripts in wheel..."
        $verifyScript = @'
import zipfile, sys
wheel_path = sys.argv[1]
z = zipfile.ZipFile(wheel_path)
scripts = [f for f in z.namelist() if f.startswith('marvex_scripts-')]
for s in scripts:
    print(f'    - {s}')
if not scripts:
    print('    WARNING: No console scripts found')
'@
        $tempPy = Join-Path $env:TEMP "marvex-verify-wheel.py"
        Set-Content -LiteralPath $tempPy -Value $verifyScript -Encoding UTF8
        $wheelContent = uv run python $tempPy $wheel.FullName 2>&1
        Remove-Item -LiteralPath $tempPy -Force
        
        Write-Host $wheelContent
        Write-Host ""
        
        return $wheel.FullName
    }
    finally {
        Pop-Location
    }
}

# ============================================================================
# Step 2: Prepare Runtime Resources
# ============================================================================

function Prepare-Runtime-Resources {
    param([string]$WheelPath)
    
    Write-Section "Step 2: Preparing Runtime Resources"
    
    # Create runtime directory
    if (-not (Test-Path $RuntimeDir)) {
        New-Item -Type Directory -Path $RuntimeDir | Out-Null
        Write-Success "Created $RuntimeDir"
    }
    
    # Copy wheel to runtime using its valid wheel filename.
    Write-Step "Copying wheel to runtime..." 2 5
    Get-ChildItem -Path $RuntimeDir -Filter "marvex-*.whl" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    $runtimeWheel = Join-Path $RuntimeDir (Split-Path $WheelPath -Leaf)
    Copy-Item -Path $WheelPath -Destination $runtimeWheel -Force
    Write-Success "Wheel copied to $runtimeWheel"

    $runtimeWheels = Join-Path $RuntimeDir "wheels"
    if (-not (Test-Path $runtimeWheels)) {
        New-Item -Type Directory -Path $runtimeWheels | Out-Null
    }
    Get-ChildItem -Path $runtimeWheels -Filter "*.whl" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    $requirementsFile = Join-Path $env:TEMP "marvex-runtime-requirements.txt"
    Write-Host "  Exporting locked runtime requirements..."
    $exportOutput = uv export --format requirements.txt --no-dev --no-emit-project --no-hashes --output-file $requirementsFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to export locked runtime requirements: $exportOutput"
    }
    $distWheelhouse = Join-Path $RepoRoot "dist"
    Write-Host "  Downloading locked dependency wheels..."
    $downloadOutput = uv run python -m pip download --only-binary=:all: --find-links $distWheelhouse --index-url https://pypi.org/simple --dest $runtimeWheels --requirement $requirementsFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error-Exit "Failed to download dependency wheels: $downloadOutput"
    }
    Remove-Item -Path $requirementsFile -Force -ErrorAction SilentlyContinue
    Write-Success "Locked dependency wheels downloaded to $runtimeWheels"
    
    # Find uv.exe (bundled or system)
    Write-Step "Locating uv executable..." 2 5
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) {
        Write-Error-Exit "uv not found in PATH"
    }
    
    # Copy uv.exe to runtime
    $uvSource = $uv.Source
    $uvDest = Join-Path $RuntimeDir "uv.exe"
    Copy-Item -Path $uvSource -Destination $uvDest -Force
    Write-Success "uv.exe copied to $RuntimeDir"
    
    Write-Host ""
}

# ============================================================================
# Step 3: Build Frontend
# ============================================================================

function Build-Frontend {
    Write-Section "Step 3: Building Frontend (React/Vite)"
    
    # Build Control Plane (shared)
    Push-Location $ControlPlaneDir
    try {
        Write-Step "Installing Control Plane dependencies..." 3 5
        Invoke-NpmCi "Control Plane"
        
        Write-Step "Building Control Plane..." 3 5
        npm run build 2>&1 | Where-Object { $_ -match 'built|entry' }
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Exit "Control Plane build failed"
        }

        Write-Success "Control Plane built"
    }
    finally {
        Pop-Location
    }

    # Verify Control Plane dist artifacts (bundled directly from dist)
    $cpDist = Join-Path $ControlPlaneDir "dist"
    if (-not (Test-Path (Join-Path $cpDist "index.html"))) {
        Write-Error-Exit "Control Plane dist missing index.html"
    }
    $cpAssets = Join-Path $cpDist "assets"
    if (-not (Test-Path $cpAssets) -or -not (Get-ChildItem -Path $cpAssets -File -ErrorAction SilentlyContinue | Select-Object -First 1)) {
        Write-Error-Exit "Control Plane dist missing built assets"
    }
    Write-Success "Control Plane dist verified"
    
    # Build Shell Frontend
    Push-Location $ShellDir
    try {
        Write-Step "Installing Shell dependencies..." 3 5
        Invoke-NpmCi "Shell"
        
        Write-Step "Building Shell frontend..." 3 5
        npm run build 2>&1 | Where-Object { $_ -match 'built|entry|vite' }
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Exit "Shell build failed"
        }
        
        Write-Success "Shell frontend built"
    }
    finally {
        Pop-Location
    }
    
    # Verify dist exists
    if (-not (Test-Path (Join-Path $ShellDir "dist"))) {
        Write-Error-Exit "Frontend build succeeded but dist/ not found"
    }
    
    Write-Host ""
}

# ============================================================================
# Step 4: Verify Frontend Assets
# ============================================================================

function Verify-Frontend-Assets {
    Write-Section "Step 4: Verifying Frontend Assets"
    
    $distPath = Join-Path $ShellDir "dist"
    
    Write-Step "Checking dist/ contents..." 4 5
    
    $required = @(
        "index.html",
        "assets"
    )
    
    foreach ($item in $required) {
        $path = Join-Path $distPath $item
        if (Test-Path $path) {
            Write-Success "$item present"
        }
        else {
            Write-Error-Exit "Missing frontend asset: $item"
        }
    }
    
    # Count JS/CSS files
    $jsFiles = @(Get-ChildItem -Path (Join-Path $distPath "assets") -Filter "*.js" -ErrorAction SilentlyContinue | Measure-Object).Count
    $cssFiles = @(Get-ChildItem -Path (Join-Path $distPath "assets") -Filter "*.css" -ErrorAction SilentlyContinue | Measure-Object).Count
    
    Write-Host "  JavaScript files: $jsFiles" -ForegroundColor Cyan
    Write-Host "  CSS files: $cssFiles" -ForegroundColor Cyan
    
    Write-Host ""
}

# ============================================================================
# Step 4b: Voice model assets + backend service binary
# ============================================================================

function Prepare-Voice-And-Service {
    Write-Section "Step 4b: Voice Models + Backend Service Binary"

    # Fetch + verify the required "Hey Marvex" / STT / TTS model assets into the
    # shell's bundled voice-asset root. Fails the build if a required asset is
    # missing so the installer never ships a broken wake word.
    $voiceAssets = Join-Path $ShellDir "voice-assets"
    if (-not (Test-Path $voiceAssets)) { New-Item -ItemType Directory -Path $voiceAssets | Out-Null }
    Write-Step "Fetching voice model assets..." 4 6
    Push-Location $RepoRoot
    try {
        uv run python scripts/fetch_voice_models.py --asset-root "$voiceAssets"
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Exit "Required voice model assets missing. Fix voice_models.manifest.json source URLs/checksums and re-run."
        }
        # The generic sherpa-onnx KWS model ships sample keywords; rewrite them so
        # the wake word is actually "Hey Marvex" (+ variants).
        uv run python scripts/generate_wakeword_keywords.py --asset-root "$voiceAssets"
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Exit "Failed to generate Hey Marvex wakeword keywords"
        }
    }
    finally {
        Pop-Location
    }
    Write-Success "Voice model assets present (Hey Marvex keywords generated)"

    # Build the always-on backend Windows service binary and place it where the
    # bundle override config (tauri.bundle.conf.json -> externalBin) expects it.
    Write-Step "Building marvex-service (backend Windows service)..." 4 6
    Push-Location $ShellTauriDir
    try {
        cargo build --release --bin marvex-service 2>&1 | Where-Object { $_ -match 'Compiling|Finished|error' }
        if ($LASTEXITCODE -ne 0) {
            Write-Error-Exit "marvex-service build failed"
        }
        $binDir = Join-Path $ShellTauriDir "binaries"
        if (-not (Test-Path $binDir)) { New-Item -ItemType Directory -Path $binDir | Out-Null }
        $svcSrc = Join-Path $ShellTauriDir "target\release\marvex-service.exe"
        $svcDst = Join-Path $binDir "marvex-service-x86_64-pc-windows-msvc.exe"
        Copy-Item -Path $svcSrc -Destination $svcDst -Force
        Write-Success "marvex-service staged for bundling"
    }
    finally {
        Pop-Location
    }
}

# ============================================================================
# Step 5: Build Tauri App + Installers
# ============================================================================

function Build-Tauri-App {
    param(
        [switch]$NoBundle = $false
    )
    
    if ($NoBundle) {
        Write-Section 'Step 5: Building Tauri App (No Bundler)'
    } else {
        Write-Section 'Step 5: Building Tauri App & Installers'
    }
    
    Push-Location $ShellDir
    try {
        if ($NoBundle) {
            Write-Step "Building Tauri app (release, --no-bundle)..." 5 5
            Write-Host "  App will compile but installers will not be generated..." -ForegroundColor Yellow
        } else {
            Write-Step "Building Tauri app (release)..." 5 5
            Write-Host "  This may take several minutes..." -ForegroundColor Yellow
        }
        
        # Resolve a Tauri CLI: local node_modules, then cargo-tauri, then npx.
        # Use an absolute config path since the build runs from the shell dir.
        $bundleConf = Join-Path $ShellTauriDir "tauri.bundle.conf.json"
        $buildArgs = @("build", "--config", "$bundleConf")
        if ($NoBundle) {
            $buildArgs += "--no-bundle"
        }
        
        $localTauri = Join-Path $ShellDir "node_modules\.bin\tauri.cmd"
        if (Test-Path $localTauri) {
            & $localTauri @buildArgs 2>&1 | Tee-Object -Variable tauriOutput | Where-Object { $_ -match 'Compiling|Finished|bundle|installer|Created' -or $_ -match "^  " }
        } elseif (Get-Command cargo-tauri -ErrorAction SilentlyContinue) {
            cargo tauri @buildArgs 2>&1 | Tee-Object -Variable tauriOutput | Where-Object { $_ -match 'Compiling|Finished|bundle|installer|Created' -or $_ -match "^  " }
        } elseif (Get-Command npx -ErrorAction SilentlyContinue) {
            npx --yes "@tauri-apps/cli" @buildArgs 2>&1 | Tee-Object -Variable tauriOutput | Where-Object { $_ -match 'Compiling|Finished|bundle|installer|Created' -or $_ -match "^  " }
        } else {
            Write-Error-Exit "Tauri CLI not found. Install with: cargo install tauri-cli  OR  npm i -D @tauri-apps/cli"
        }

        if ($LASTEXITCODE -ne 0) {
            Write-Error-Exit "Tauri build failed. Full output: `n$tauriOutput"
        }
        
        if ($NoBundle) {
            Write-Success "Tauri app built successfully (no bundle/installer generated)"
        } else {
            Write-Success "Tauri app built successfully"
        }
    }
    finally {
        Pop-Location
    }
    
    Write-Host ""
}

# ============================================================================
# Step 6: Locate Installers
# ============================================================================

function Locate-Installers {
    Write-Section "Step 6: Installer Artifacts"
    
    $bundleDir = Join-Path $ShellTauriDir "target\release\bundle"
    
    Write-Step "Searching for installers..." 6 5
    
    if (-not (Test-Path $bundleDir)) {
        Write-Error-Exit "Bundle directory not found: $bundleDir"
    }
    
    # Find NSIS installer
    $nsisInstaller = Get-ChildItem -Path $bundleDir -Recurse -Filter "Marvex_*_x64-setup.exe" 2>$null | 
                     Sort-Object LastWriteTime -Descending | 
                     Select-Object -First 1
    
    if ($nsisInstaller) {
        Write-Success "NSIS Installer: $($nsisInstaller.Name)"
        Write-Host "  Location: $($nsisInstaller.FullName)" -ForegroundColor Cyan
        Write-Host "  Size: $([Math]::Round($nsisInstaller.Length / 1MB, 2)) MB" -ForegroundColor Cyan
    }
    else {
        Write-Host "  ⚠ NSIS installer not found" -ForegroundColor Yellow
    }
    
    # Find MSI installer
    $msiInstaller = Get-ChildItem -Path $bundleDir -Recurse -Filter "*.msi" 2>$null | 
                    Sort-Object LastWriteTime -Descending | 
                    Select-Object -First 1
    
    if ($msiInstaller) {
        Write-Success "MSI Installer: $($msiInstaller.Name)"
        Write-Host "  Location: $($msiInstaller.FullName)" -ForegroundColor Cyan
        Write-Host "  Size: $([Math]::Round($msiInstaller.Length / 1MB, 2)) MB" -ForegroundColor Cyan
    }
    else {
        Write-Host "  ⚠ MSI installer not found" -ForegroundColor Yellow
    }
    
    Write-Host ""
}

# ============================================================================
# Summary & Next Steps
# ============================================================================

function Print-Summary {
    Write-Section "Build Complete! ✓"
    
    Write-Host "Installer artifacts are located in:" -ForegroundColor Green
    Write-Host "  $ShellTauriDir\target\release\bundle\" -ForegroundColor Cyan
    Write-Host ""
    
    Write-Host "Runtime packaging (Tier 1: Production):" -ForegroundColor Green
    Write-Host "  ✓ Setuptools console scripts (not frozen PyInstaller)" -ForegroundColor Green
    Write-Host "  ✓ Dynamic Python runtime in ~/.marvex/runtime/venv/" -ForegroundColor Green
    Write-Host "  ✓ Supports runtime package installation via Deps tab" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Test the installer on a clean Windows machine" -ForegroundColor Cyan
    Write-Host "  2. Run smoke tests (see apps/shell/README.md)" -ForegroundColor Cyan
    Write-Host "  3. Verify no terminal windows appear during runtime" -ForegroundColor Cyan
    Write-Host "  4. Check ~/.marvex/runtime/manifest.json after first run" -ForegroundColor Cyan
    Write-Host ""
}

# ============================================================================
# Main
# ============================================================================

function Main {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "║             MARVEX INSTALLER BUILD SCRIPT                  ║" -ForegroundColor Magenta
    Write-Host "║         Tier 1: Production (Setuptools Console Scripts)    ║" -ForegroundColor Magenta
    if ($SkipInstaller) {
        Write-Host "║             (Skipping final installer generation)           ║" -ForegroundColor Yellow
    }
    Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
    Write-Host ""
    
    Validate-Environment
    Clean-Previous-Build
    
    $wheel = Build-Python-Wheel
    Prepare-Runtime-Resources -WheelPath $wheel
    Build-Frontend
    Verify-Frontend-Assets
    Prepare-Voice-And-Service
    
    if ($SkipInstaller) {
        Build-Tauri-App -NoBundle
        Write-Section "Build Summary (Skip Installer Mode)"
        Write-Host "✓ Tauri app compiled successfully (no installer bundled)" -ForegroundColor Green
        Write-Host ""
        Write-Host "Compiled app location:" -ForegroundColor Cyan
        Write-Host "  $ShellTauriDir\target\release\marvex-service.exe" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To generate the final installer, run:" -ForegroundColor Cyan
        Write-Host "  .\build-installer.ps1" -ForegroundColor Yellow
        Write-Host ""
    }
    else {
        Build-Tauri-App
        Locate-Installers
    }
    
    Print-Summary
}

# Run
Main

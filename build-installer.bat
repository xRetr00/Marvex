@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Build Marvex Windows installer (NSIS/MSI) from source.
rem Usage:
rem   build-installer.bat [-SkipValidation] [-Clean] [-Verbose]

set "SkipValidation=0"
set "Clean=0"
set "Verbose=0"

call :ParseArgs %*

set "RepoRoot=%~dp0"
if "%RepoRoot:~-1%"=="\" set "RepoRoot=%RepoRoot:~0,-1%"
set "ShellDir=%RepoRoot%\apps\shell"
set "ShellSrcDir=%ShellDir%\src"
set "ShellTauriDir=%ShellDir%\src-tauri"
set "ControlPlaneDir=%RepoRoot%\apps\control_plane_web"
set "RuntimeDir=%ShellDir%\runtime"
set "DistDir=%ShellDir%\dist"

call :Banner

call :ValidateEnvironment
if errorlevel 1 exit /b 1

call :CleanPreviousBuild
if errorlevel 1 exit /b 1

call :BuildPythonWheel
if errorlevel 1 exit /b 1

call :PrepareRuntimeResources
if errorlevel 1 exit /b 1

call :BuildFrontend
if errorlevel 1 exit /b 1

call :VerifyFrontendAssets
if errorlevel 1 exit /b 1

call :PrepareVoiceAndService
if errorlevel 1 exit /b 1

call :BuildTauriApp
if errorlevel 1 exit /b 1

call :LocateInstallers
if errorlevel 1 exit /b 1

call :PrintSummary
exit /b 0

rem ============================================================================
rem Helpers
rem ============================================================================

:ParseArgs
if "%~1"=="" goto :eof
set "arg=%~1"
if /I "%arg%"=="-SkipValidation" set "SkipValidation=1"
if /I "%arg%"=="/SkipValidation" set "SkipValidation=1"
if /I "%arg%"=="-Clean" set "Clean=1"
if /I "%arg%"=="/Clean" set "Clean=1"
if /I "%arg%"=="-Verbose" set "Verbose=1"
if /I "%arg%"=="/Verbose" set "Verbose=1"
shift
goto :ParseArgs

:Banner
echo.
echo ================================================================
echo   MARVEX INSTALLER BUILD SCRIPT
echo   Tier 1: Production (Setuptools Console Scripts)
echo ================================================================
echo.
exit /b 0

:WriteSection
echo.
echo ================================================================
echo   %~1
echo ================================================================
echo.
exit /b 0

:WriteStep
echo [%~2/%~3] %~1
exit /b 0

:WriteSuccess
echo [OK] %~1
exit /b 0

:Die
echo [ERROR] %~1
exit /b 1

rem ============================================================================
rem Validation
rem ============================================================================

:ValidateEnvironment
if "%SkipValidation%"=="1" (
    echo [WARN] Skipping environment validation
    exit /b 0
)

call :WriteSection "Validating Environment"

set "nodeVersion="
for /f "delims=" %%A in ('node --version 2^>nul') do set "nodeVersion=%%A"
if not defined nodeVersion (
    call :Die "Node.js not found. Install from https://nodejs.org/"
    exit /b 1
)
call :WriteSuccess "Node.js: !nodeVersion!"

set "npmVersion="
for /f "delims=" %%A in ('npm --version 2^>nul') do set "npmVersion=%%A"
if not defined npmVersion (
    call :Die "npm not found"
    exit /b 1
)
call :WriteSuccess "npm: !npmVersion!"

set "cargoVersion="
for /f "delims=" %%A in ('cargo --version 2^>nul') do set "cargoVersion=%%A"
if not defined cargoVersion (
    call :Die "Cargo not found. Install from https://rustup.rs/"
    exit /b 1
)
call :WriteSuccess "Cargo: !cargoVersion!"

set "uvVersion="
for /f "delims=" %%A in ('uv --version 2^>nul') do set "uvVersion=%%A"
if not defined uvVersion (
    call :Die "uv not found. Install with: pip install uv"
    exit /b 1
)
call :WriteSuccess "uv: !uvVersion!"

set "pythonVersion="
for /f "delims=" %%A in ('python --version 2^>nul') do set "pythonVersion=%%A"
if not defined pythonVersion (
    call :Die "Python not found. Install Python 3.11+ from https://www.python.org/"
    exit /b 1
)
call :WriteSuccess "Python: !pythonVersion!"

set "pyMajor="
set "pyMinor="
set "lineIndex=0"
for /f "delims=" %%A in ('python -c "import sys; print(sys.version_info.major); print(sys.version_info.minor)" 2^>nul') do (
    set /a lineIndex+=1
    if !lineIndex! EQU 1 set "pyMajor=%%A"
    if !lineIndex! EQU 2 set "pyMinor=%%A"
)
if not defined pyMajor (
    call :Die "Python 3.11 or higher required."
    exit /b 1
)
set "pyVer=!pyMajor!.!pyMinor!"
if !pyMajor! LSS 3 (
    call :Die "Python 3.11 or higher required. Found: !pyVer!"
    exit /b 1
)
if !pyMajor! EQU 3 if !pyMinor! LSS 11 (
    call :Die "Python 3.11 or higher required. Found: !pyVer!"
    exit /b 1
)

echo.
exit /b 0

rem ============================================================================
rem Clean
rem ============================================================================

:CleanPreviousBuild
if "%Clean%"=="0" exit /b 0

call :WriteSection "Cleaning Previous Build"

set "paths[0]=%ShellDir%\dist"
set "paths[1]=%ShellDir%\build"
set "paths[2]=%ShellDir%\node_modules"
set "paths[3]=%ShellTauriDir%\target"
set "paths[4]=%ControlPlaneDir%\dist"
set "paths[5]=%ControlPlaneDir%\node_modules"

for /l %%I in (0,1,5) do (
    set "target=!paths[%%I]!"
    if exist "!target!" (
        echo Removing: !target!
        rmdir /s /q "!target!"
    )
)

call :WriteSuccess "Previous build cleaned"
echo.
exit /b 0

rem ============================================================================
rem Step 1: Build Python Wheel
rem ============================================================================

:BuildPythonWheel
call :WriteSection "Step 1: Building Python Wheel"

pushd "%RepoRoot%"
call :WriteStep "Building marvex wheel..." 1 6
uv build --wheel
if errorlevel 1 (
    popd
    call :Die "Failed to build Python wheel"
    exit /b 1
)

set "WheelPath="
for /f "delims=" %%F in ('dir /b /a-d /o-d "!RepoRoot!\dist\marvex-*.whl" 2^>nul') do (
    set "WheelPath=!RepoRoot!\dist\%%F"
    goto :WheelFound
)
:WheelFound
if not defined WheelPath (
    popd
    call :Die "Wheel build succeeded but no .whl file found in dist\"
    exit /b 1
)
call :WriteSuccess "Wheel built: !WheelPath!"

echo   Verifying console scripts in wheel...
set "verifyCmd=import zipfile, sys; wheel_path=sys.argv[1]; z=zipfile.ZipFile(wheel_path); scripts=[f for f in z.namelist() if f.startswith('marvex_scripts-')]; [print('    - '+s) for s in scripts]; print('    WARNING: No console scripts found') if not scripts else None"
uv run python -c "!verifyCmd!" "!WheelPath!"
if errorlevel 1 (
    popd
    call :Die "Failed to verify wheel contents"
    exit /b 1
)
echo.

popd
exit /b 0

rem ============================================================================
rem Step 2: Prepare Runtime Resources
rem ============================================================================

:PrepareRuntimeResources
call :WriteSection "Step 2: Preparing Runtime Resources"

if not exist "%RuntimeDir%" (
    mkdir "%RuntimeDir%"
    call :WriteSuccess "Created %RuntimeDir%"
)

call :WriteStep "Copying wheel to runtime..." 2 6
copy /y "%WheelPath%" "%RuntimeDir%" >nul
if errorlevel 1 (
    call :Die "Failed to copy wheel to runtime"
    exit /b 1
)
call :WriteSuccess "Wheel copied to %RuntimeDir%"

call :WriteStep "Locating uv executable..." 2 6
set "uvPath="
for /f "delims=" %%A in ('where uv 2^>nul') do (
    set "uvPath=%%A"
    goto :FoundUv
)
:FoundUv
if not defined uvPath (
    call :Die "uv not found in PATH"
    exit /b 1
)

copy /y "!uvPath!" "%RuntimeDir%\uv.exe" >nul
if errorlevel 1 (
    call :Die "Failed to copy uv.exe to runtime"
    exit /b 1
)
call :WriteSuccess "uv.exe copied to %RuntimeDir%"

echo.
exit /b 0

rem ============================================================================
rem Step 3: Build Frontend
rem ============================================================================

:BuildFrontend
call :WriteSection "Step 3: Building Frontend (React/Vite)"

pushd "%ControlPlaneDir%"
call :WriteStep "Installing Control Plane dependencies..." 3 6
call npm ci
set "npmExit=!ERRORLEVEL!"
if not "!npmExit!"=="0" (
    popd
    call :Die "npm ci failed for Control Plane. Close running Node/Vite dev servers that may lock node_modules native packages, then retry."
    exit /b !npmExit!
)

call :WriteStep "Building Control Plane..." 3 6
call npm run build
if errorlevel 1 (
    popd
    call :Die "Control Plane build failed"
    exit /b 1
)
call :WriteSuccess "Control Plane built"
popd

rem Stage the built Control Plane SPA into the shell so it is bundled and served
rem same-origin by the control plane server for the shell's Control Plane window.
if exist "%ShellDir%\control_plane_web" rmdir /s /q "%ShellDir%\control_plane_web"
mkdir "%ShellDir%\control_plane_web"
xcopy /e /i /y "%ControlPlaneDir%\dist\*" "%ShellDir%\control_plane_web\" >nul
if not exist "%ShellDir%\control_plane_web\index.html" (
    call :Die "Control Plane staged resource missing index.html"
    exit /b 1
)
if not exist "%ShellDir%\control_plane_web\assets" (
    call :Die "Control Plane staged resource missing built assets"
    exit /b 1
)
dir /b "%ShellDir%\control_plane_web\assets\*" >nul 2>&1
if errorlevel 1 (
    call :Die "Control Plane staged resource missing built assets"
    exit /b 1
)
call :WriteSuccess "Control Plane SPA staged into shell resources"

pushd "%ShellDir%"
call :WriteStep "Installing Shell dependencies..." 3 6
call npm ci
set "npmExit=!ERRORLEVEL!"
if not "!npmExit!"=="0" (
    popd
    call :Die "npm ci failed for Shell. Close running Node/Vite dev servers that may lock node_modules native packages, then retry."
    exit /b !npmExit!
)

call :WriteStep "Building Shell frontend..." 3 6
call npm run build
if errorlevel 1 (
    popd
    call :Die "Shell build failed"
    exit /b 1
)
call :WriteSuccess "Shell frontend built"
popd

if not exist "%ShellDir%\dist" (
    call :Die "Frontend build succeeded but dist\ not found"
    exit /b 1
)
echo.
exit /b 0

rem ============================================================================
rem Step 4: Verify Frontend Assets
rem ============================================================================

:VerifyFrontendAssets
call :WriteSection "Step 4: Verifying Frontend Assets"

set "distPath=%ShellDir%\dist"
call :WriteStep "Checking dist\ contents..." 4 6

if exist "%distPath%\index.html" (
    call :WriteSuccess "index.html present"
) else (
    call :Die "Missing frontend asset: index.html"
    exit /b 1
)

if exist "%distPath%\assets" (
    call :WriteSuccess "assets present"
) else (
    call :Die "Missing frontend asset: assets"
    exit /b 1
)

set "jsCount=0"
for /f %%A in ('dir /b /a-d "%distPath%\assets\*.js" 2^>nul ^| find /c /v ""') do set "jsCount=%%A"
set "cssCount=0"
for /f %%A in ('dir /b /a-d "%distPath%\assets\*.css" 2^>nul ^| find /c /v ""') do set "cssCount=%%A"

echo   JavaScript files: !jsCount!
echo   CSS files: !cssCount!
echo.
exit /b 0

rem ============================================================================
rem Step 5: Build Tauri App + Installers
rem ============================================================================

:PrepareVoiceAndService
call :WriteSection "Step 4b: Voice Models + Backend Service Binary"

if not exist "%ShellDir%\voice-assets" mkdir "%ShellDir%\voice-assets"
call :WriteStep "Fetching voice model assets..." 4 6
pushd "%RepoRoot%"
call uv run python scripts\fetch_voice_models.py --asset-root "%ShellDir%\voice-assets"
if errorlevel 1 (
    popd
    call :Die "Required voice model assets missing. Fix voice_models.manifest.json and re-run."
    exit /b 1
)
rem Rewrite the generic KWS keywords so the wake word is actually "Hey Marvex".
call uv run python scripts\generate_wakeword_keywords.py --asset-root "%ShellDir%\voice-assets"
if errorlevel 1 (
    popd
    call :Die "Failed to generate Hey Marvex wakeword keywords"
    exit /b 1
)
popd
call :WriteSuccess "Voice model assets present (Hey Marvex keywords generated)"

call :WriteStep "Building marvex-service (backend Windows service)..." 4 6
pushd "%ShellTauriDir%"
call cargo build --release --bin marvex-service
if errorlevel 1 (
    popd
    call :Die "marvex-service build failed"
    exit /b 1
)
if not exist "%ShellTauriDir%\binaries" mkdir "%ShellTauriDir%\binaries"
copy /y "%ShellTauriDir%\target\release\marvex-service.exe" "%ShellTauriDir%\binaries\marvex-service-x86_64-pc-windows-msvc.exe" >nul
popd
call :WriteSuccess "marvex-service staged for bundling"
goto :eof

:BuildTauriApp
call :WriteSection "Step 5: Building Tauri App and Installers"

pushd "%ShellDir%"
call :WriteStep "Building Tauri app (release)..." 5 6
echo   This may take several minutes...

set "tauriLocalCmd=%ShellDir%\node_modules\.bin\tauri.cmd"
set "tauriLocalExe=%ShellDir%\node_modules\.bin\tauri.exe"
set "BundleConf=%ShellTauriDir%\tauri.bundle.conf.json"
if exist "!tauriLocalCmd!" (
    call "!tauriLocalCmd!" build --config "!BundleConf!"
) else if exist "!tauriLocalExe!" (
    call "!tauriLocalExe!" build --config "!BundleConf!"
) else (
    where cargo-tauri >nul 2>&1
    if not errorlevel 1 (
        call cargo tauri build --config "!BundleConf!"
    ) else (
        where npx >nul 2>&1
        if not errorlevel 1 (
            call npx --yes @tauri-apps/cli build --config "!BundleConf!"
        ) else (
            popd
            call :Die "Tauri CLI not found. Install with: cargo install tauri-cli  OR  npm i -D @tauri-apps/cli"
            exit /b 1
        )
    )
)
if errorlevel 1 (
    popd
    call :Die "Tauri build failed"
    exit /b 1
)
call :WriteSuccess "Tauri app built successfully"
popd

echo.
exit /b 0

rem ============================================================================
rem Step 6: Locate Installers
rem ============================================================================

:LocateInstallers
call :WriteSection "Step 6: Installer Artifacts"

set "bundleDir=%ShellTauriDir%\target\release\bundle"
call :WriteStep "Searching for installers..." 6 6

if not exist "%bundleDir%" (
    call :Die "Bundle directory not found: %bundleDir%"
    exit /b 1
)

set "nsisInstaller="
for /f "delims=" %%F in ('dir /b /a-d /s /o-d "%bundleDir%\Marvex_*_x64-setup.exe" 2^>nul') do (
    set "nsisInstaller=%%F"
    goto :FoundNsis
)
:FoundNsis
if defined nsisInstaller (
    for %%A in ("!nsisInstaller!") do (
        set "nsisName=%%~nxA"
        set "nsisSize=%%~zA"
    )
    call :WriteSuccess "NSIS Installer: !nsisName!"
    set /a nsisSizeMb=!nsisSize!/1048576
    echo   Location: !nsisInstaller!
    echo   Size: !nsisSizeMb! MB
) else (
    echo   [WARN] NSIS installer not found
)

set "msiInstaller="
for /f "delims=" %%F in ('dir /b /a-d /s /o-d "%bundleDir%\*.msi" 2^>nul') do (
    set "msiInstaller=%%F"
    goto :FoundMsi
)
:FoundMsi
if defined msiInstaller (
    for %%A in ("!msiInstaller!") do (
        set "msiName=%%~nxA"
        set "msiSize=%%~zA"
    )
    call :WriteSuccess "MSI Installer: !msiName!"
    set /a msiSizeMb=!msiSize!/1048576
    echo   Location: !msiInstaller!
    echo   Size: !msiSizeMb! MB
) else (
    echo   [WARN] MSI installer not found
)

echo.
exit /b 0

rem ============================================================================
rem Summary
rem ============================================================================

:PrintSummary
call :WriteSection "Build Complete!"

echo Installer artifacts are located in:
echo   %ShellTauriDir%\target\release\bundle\
echo.
echo Runtime packaging (Tier 1: Production):
echo   [OK] Setuptools console scripts (not frozen PyInstaller)
echo   [OK] Dynamic Python runtime in ^~\.marvex\runtime\venv\
echo   [OK] Supports runtime package installation via Deps tab
echo.
echo Next steps:
echo   1. Test the installer on a clean Windows machine
echo   2. Run smoke tests (see apps\shell\README.md)
echo   3. Verify no terminal windows appear during runtime
echo   4. Check ^~\.marvex\runtime\manifest.json after first run
echo.
exit /b 0

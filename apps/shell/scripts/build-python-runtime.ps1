param(
    [string[]]$Targets = @("core", "provider_worker", "intent_worker", "tool_worker", "voice_worker")
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$packagingDir = Join-Path $repoRoot "apps\shell\packaging"
$distRoot = Join-Path $repoRoot "apps\shell\dist\python"
$buildRoot = Join-Path $repoRoot "apps\shell\build\pyinstaller"

$specByTarget = @{
    "core" = "core.spec"
    "provider_worker" = "provider_worker.spec"
    "intent_worker" = "intent_worker.spec"
    "tool_worker" = "tool_worker.spec"
    "voice_worker" = "voice_worker.spec"
}

foreach ($target in $Targets) {
    if (-not $specByTarget.ContainsKey($target)) {
        throw "Unsupported target '$target'. Supported: $($specByTarget.Keys -join ', ')"
    }

    $specName = $specByTarget[$target]
    $specPath = Join-Path $packagingDir $specName
    $targetBuildDir = Join-Path $buildRoot $target

    if (-not (Test-Path $specPath)) {
        throw "Missing spec file: $specPath"
    }

    Write-Host "Building $target from $specName"
    uv run python -m PyInstaller --noconfirm --distpath $distRoot --workpath $targetBuildDir $specPath
}

param(
    [string]$ServiceExe,
    [int]$TimeoutSeconds = 120,
    [switch]$KeepTemp
)

$ErrorActionPreference = "Stop"

# Contract endpoints: /health, /control/health, /control/state,
# /control/state/stream, and /v1/turns.

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
if (-not $ServiceExe) {
    $ServiceExe = Join-Path $RepoRoot "apps\shell\src-tauri\target\release\marvex-service.exe"
}
$ServiceExe = [System.IO.Path]::GetFullPath($ServiceExe)
$SmokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("marvex-packaged-runtime-smoke-" + [guid]::NewGuid().ToString("N"))
$ProgramDataRoot = Join-Path $SmokeRoot "ProgramData"
$ConsoleStopFile = Join-Path $SmokeRoot "stop-console"
$Process = $null

function Write-Step([string]$Message) {
    Write-Host "[smoke] $Message"
}

function Test-PortOpen([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $result.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($result)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Assert-PortFree([int]$Port) {
    if (Test-PortOpen $Port) {
        throw "port $Port is already in use before smoke startup"
    }
}

function Assert-PortClosed([int]$Port) {
    if (Test-PortOpen $Port) {
        throw "port $Port is still occupied after smoke shutdown"
    }
}

function Stage-DirectoryResource([string]$Source, [string]$Destination) {
    if (-not (Test-Path $Source)) {
        return
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

function Stage-DefaultRuntimeResources {
    $defaultServiceExe = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "apps\shell\src-tauri\target\release\marvex-service.exe"))
    if ($ServiceExe -ne $defaultServiceExe) {
        return
    }

    $serviceDir = Split-Path -Parent $ServiceExe
    $runtimeDir = Join-Path $RepoRoot "apps\shell\runtime"
    $wheel = Get-ChildItem -Path $runtimeDir -Filter "marvex-*.whl" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($wheel) {
        Get-ChildItem -Path $serviceDir -Filter "marvex-*.whl" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        Copy-Item -LiteralPath $wheel.FullName -Destination (Join-Path $serviceDir $wheel.Name) -Force
    }

    $uv = Join-Path $runtimeDir "uv.exe"
    if (Test-Path $uv) {
        Copy-Item -LiteralPath $uv -Destination (Join-Path $serviceDir "uv.exe") -Force
    }

    Stage-DirectoryResource `
        (Join-Path $RepoRoot "apps\control_plane_web\dist") `
        (Join-Path $serviceDir "control_plane_web")
    Stage-DirectoryResource `
        (Join-Path $RepoRoot "apps\shell\voice-assets") `
        (Join-Path $serviceDir "voice-assets")
}

function Wait-Until([scriptblock]$Predicate, [string]$Description) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (& $Predicate) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "timed out waiting for $Description"
}

function Request-TokenLease {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pipe = $null
        try {
            $pipe = New-Object System.IO.Pipes.NamedPipeClientStream(
                ".",
                "Marvex.TokenHandoff.v1",
                [System.IO.Pipes.PipeDirection]::InOut,
                [System.IO.Pipes.PipeOptions]::None
            )
            $pipe.Connect(1000)
            $encoding = New-Object System.Text.UTF8Encoding($false)
            $writer = New-Object System.IO.StreamWriter($pipe, $encoding, 1024, $true)
            $reader = New-Object System.IO.StreamReader($pipe, $encoding, $false, 1024, $true)
            $writer.AutoFlush = $true
            $writer.WriteLine('{"request":"token_lease"}')
            $line = $reader.ReadLine()
            if ($line) {
                return $line | ConvertFrom-Json
            }
        } catch {
            Start-Sleep -Milliseconds 250
        } finally {
            if ($pipe) {
                $pipe.Dispose()
            }
        }
    }
    throw "token lease pipe did not respond"
}

function Invoke-RuntimeGet([string]$Url, [string]$Token) {
    Invoke-RestMethod `
        -Uri $Url `
        -Method Get `
        -Headers @{ Authorization = "Bearer $Token" } `
        -TimeoutSec 15
}

function Invoke-RuntimePost([string]$Url, [string]$Token, [object]$Body) {
    $json = $Body | ConvertTo-Json -Depth 12
    Invoke-RestMethod `
        -Uri $Url `
        -Method Post `
        -Headers @{ Authorization = "Bearer $Token" } `
        -Body $json `
        -ContentType "application/json" `
        -TimeoutSec 90
}

function Read-StateStreamOnce([string]$Token) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", 8766)
        $stream = $client.GetStream()
        $stream.ReadTimeout = 5000
        $request = "GET /control/state/stream HTTP/1.1`r`nHost: 127.0.0.1:8766`r`nAccept: text/event-stream`r`nAuthorization: Bearer $Token`r`nConnection: close`r`n`r`n"
        $bytes = [System.Text.Encoding]::ASCII.GetBytes($request)
        $stream.Write($bytes, 0, $bytes.Length)
        $buffer = New-Object byte[] 4096
        $read = $stream.Read($buffer, 0, $buffer.Length)
        if ($read -le 0) {
            throw "state stream returned no bytes"
        }
        $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $read)
        if ($text -notmatch "200 OK") {
            throw "state stream did not return HTTP 200"
        }
        return $text
    } finally {
        $client.Close()
    }
}

function Assert-Manifest([string]$ManifestPath, [string]$Token) {
    if (-not (Test-Path $ManifestPath)) {
        throw "runtime manifest missing: $ManifestPath"
    }
    $text = Get-Content -Path $ManifestPath -Raw
    if ($text.Contains($Token)) {
        throw "runtime manifest contains raw token material"
    }
    $manifest = $text | ConvertFrom-Json
    $names = @($manifest.services | ForEach-Object { $_.name })
    $expected = @("core", "voice_worker")
    if (($names -join ",") -ne ($expected -join ",")) {
        throw "runtime manifest services were '$($names -join ",")', expected '$($expected -join ",")'"
    }
    foreach ($coreOwned in @("provider_worker", "intent_worker", "tool_worker")) {
        if ($names -contains $coreOwned) {
            throw "runtime manifest incorrectly lists Core-owned worker: $coreOwned"
        }
    }
}

try {
    if (-not (Test-Path $ServiceExe)) {
        throw "release service binary missing: $ServiceExe"
    }
    Stage-DefaultRuntimeResources
    New-Item -ItemType Directory -Force -Path $ProgramDataRoot | Out-Null
    Assert-PortFree 8765
    Assert-PortFree 8766

    Write-Step "starting marvex-service --console"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $ServiceExe
    $psi.Arguments = "--console"
    $psi.WorkingDirectory = $RepoRoot
    $psi.UseShellExecute = $false
    $psi.Environment["ProgramData"] = $ProgramDataRoot
    $psi.Environment["MARVEX_SERVICE_CONSOLE_STOP_FILE"] = $ConsoleStopFile
    $Process = New-Object System.Diagnostics.Process
    $Process.StartInfo = $psi
    if (-not $Process.Start()) {
        throw "failed to start service process"
    }

    Write-Step "requesting token lease"
    $lease = Request-TokenLease
    if (-not $lease.auth_token_present -or $lease.token_value_logged) {
        throw "token lease metadata is unsafe"
    }
    $token = [string]$lease.token
    if (-not $token) {
        throw "token lease returned no token"
    }

    Write-Step "waiting for Core and Control Plane"
    Wait-Until { Test-PortOpen 8765 } "Core port 8765"
    Wait-Until { Test-PortOpen 8766 } "Control Plane port 8766"

    Write-Step "checking health endpoints"
    $coreHealth = Invoke-RuntimeGet "$($lease.core_base_url)/health" $token
    if ($coreHealth.service -ne "marvex-core-service") {
        throw "unexpected Core health service: $($coreHealth.service)"
    }
    $controlHealth = Invoke-RuntimeGet "$($lease.control_base_url)/health" $token
    if ($controlHealth.schema_version -ne "1" -or $controlHealth.status -ne "ok") {
        throw "unexpected Control Plane health response"
    }

    Write-Step "checking Control Plane state and stream"
    $state = Invoke-RuntimeGet "$($lease.control_base_url)/state" $token
    if (-not $state.schema_version) {
        throw "control state response is missing schema_version"
    }
    $streamText = Read-StateStreamOnce $token
    if ($streamText -notmatch "data:") {
        throw "state stream returned no SSE data"
    }

    Write-Step "submitting worker-backed turn"
    $turnBody = @{
        schema_version = "0.1.1-draft"
        execution_mode = "assistant_runtime_fake_provider"
        assistant_turn_input = @{
            schema_version = "0.1.1-draft"
            trace_id = "trace-packaged-runtime-smoke"
            turn_id = "turn-packaged-runtime-smoke"
            input_event_id = "event-packaged-runtime-smoke"
            session_ref = @{ ref_type = "session"; ref_id = "session-packaged-runtime-smoke" }
            identity_ref = $null
            user_visible_input = "Hello through packaged runtime"
            assistant_mode = "default"
            policy_context = @{ requested_capabilities = @(); sensitivity = "normal" }
            metadata = @{ source = "packaged_runtime_smoke" }
        }
        model = "fake-model"
        instructions = $null
        previous_response_id = $null
        provider_options = @{}
    }
    $turn = Invoke-RuntimePost "$($lease.core_base_url)/v1/turns" $token $turnBody
    if ($turn.metadata.provider_boundary -ne "provider_worker_process") {
        throw "turn did not use worker-backed provider path"
    }
    if ($turn.assistant_final_response.text -ne "fake provider response") {
        throw "unexpected turn response"
    }

    Write-Step "checking runtime manifest"
    $manifestPath = Join-Path $ProgramDataRoot "Marvex\data\runtime\manifest.json"
    Assert-Manifest $manifestPath $token

    Write-Step "packaged runtime smoke passed"
} finally {
    if ($Process -and -not $Process.HasExited) {
        Write-Step "stopping marvex-service --console"
        New-Item -ItemType File -Force -Path $ConsoleStopFile | Out-Null
        if ($Process.WaitForExit(20000)) {
            $Process = $null
        }
    }
    if ($Process -and -not $Process.HasExited) {
        try {
            $Process.Kill($true)
        } catch {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        }
        $Process.WaitForExit(10000) | Out-Null
    }
    Start-Sleep -Seconds 2
    Assert-PortClosed 8765
    Assert-PortClosed 8766
    if (-not $KeepTemp -and (Test-Path $SmokeRoot)) {
        Remove-Item -Path $SmokeRoot -Recurse -Force -ErrorAction SilentlyContinue
    } elseif ($KeepTemp) {
        Write-Step "kept smoke temp root: $SmokeRoot"
    }
}

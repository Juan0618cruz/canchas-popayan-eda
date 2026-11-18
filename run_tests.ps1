<#
.SYNOPSIS
    Script maestro de ejecución y reporte de pruebas automatizadas — Canchas Popayán EDA.
.DESCRIPTION
    Ejecuta las suites unitarias y de integración (python -m pytest + FastAPI TestClient)
    para api_gateway, ms_usuarios, ms_canchas, ms_reservas, ms_pagos y ms_notificaciones,
    mostrando un reporte consolidado de casos PASSED / FAILED para evidencia técnica.
#>

param(
    [switch]$UseDocker,
    [switch]$ReinstallDeps
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   CANCHAS POPAYAN EDA - SUITE DE PRUEBAS AUTOMATIZADAS (PYTEST)      " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ("Fecha de ejecucion : {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray
Write-Host ("Directorio raiz    : {0}" -f $RootDir) -ForegroundColor Gray
Write-Host ""

function Test-PythonBinary([string]$Candidate) {
    try {
        $prevPref = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $out = & $Candidate -c "import sys; print(sys.executable)" 2>$null
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prevPref
        return ($code -eq 0 -and -not [string]::IsNullOrWhiteSpace($out))
    } catch {
        return $false
    }
}

function Find-LocalPython {
    $candidates = @()
    $venvPython = Join-Path $RootDir ".venv-tests\Scripts\python.exe"
    if (Test-Path $venvPython) { $candidates += $venvPython }

    foreach ($cmd in @("python", "python3", "py")) {
        $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($resolved -and ($resolved.Source -notlike "*\WindowsApps\*")) {
            $candidates += $resolved.Source
        }
    }

    $searchRoots = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*",
        "C:\Python3*",
        "C:\Program Files\Python3*"
    )
    foreach ($pattern in $searchRoots) {
        Get-Item $pattern -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object {
            $exe = Join-Path $_.FullName "python.exe"
            if (Test-Path $exe) { $candidates += $exe }
        }
    }

    foreach ($c in ($candidates | Select-Object -Unique)) {
        if (Test-PythonBinary $c) { return $c }
    }
    return $null
}

$Suites = @(
    @{ Name = "Autenticacion y Roles (ms_usuarios + api_gateway)"; File = "tests/test_ms_usuarios.py" },
    @{ Name = "Complejos y Mantenimiento (ms_canchas)";            File = "tests/test_ms_canchas.py" },
    @{ Name = "Ciclo de Vida de Reservas (ms_reservas)";           File = "tests/test_ms_reservas.py" },
    @{ Name = "Pasarela Wompi Colombia (ms_pagos)";                File = "tests/test_ms_pagos.py" },
    @{ Name = "Eventos EDA y SMTP HTML (ms_notificaciones)";       File = "tests/test_ms_notificaciones.py" }
)

$PythonExe = $null
$RunnerMode = "local"

if (-not $UseDocker) {
    $PythonExe = Find-LocalPython
}

if ($PythonExe) {
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $hasDeps = $false
    if (-not $ReinstallDeps) {
        & $PythonExe -c "import pytest, fastapi, httpx, sqlalchemy, jose, passlib" 2>$null
        $hasDeps = ($LASTEXITCODE -eq 0)
    }

    if (-not $hasDeps) {
        $venvDir = Join-Path $RootDir ".venv-tests"
        $venvPy  = Join-Path $venvDir "Scripts\python.exe"
        if (-not (Test-Path $venvPy)) {
            Write-Host "[SETUP] Creando entorno virtual aislado en .venv-tests ..." -ForegroundColor Yellow
            & $PythonExe -m venv $venvDir
        }
        $PythonExe = $venvPy
        Write-Host "[SETUP] Instalando dependencias de prueba (tests/requirements-test.txt) ..." -ForegroundColor Yellow
        & $PythonExe -m pip install --upgrade pip --root-user-action=ignore -q
        & $PythonExe -m pip install --root-user-action=ignore -q -r (Join-Path $RootDir "tests\requirements-test.txt")
    }
    $ErrorActionPreference = $prevPref
} elseif (Get-Command docker -ErrorAction SilentlyContinue) {
    $RunnerMode = "docker"
    Write-Host "[INFO] Ejecutando pruebas en contenedor Docker unico (python:3.12-slim + cache de dependencias) ..." -ForegroundColor Yellow
} else {
    Write-Host "[ERROR] No se encontro Python 3 ni Docker disponible en el sistema." -ForegroundColor Red
    exit 1
}

$Results = @()
$TotalPassed = 0
$TotalFailed = 0
$AnyFailure = $false

if ($RunnerMode -eq "local") {
    Write-Host ("[INFO] Interprete Python: {0}" -f $PythonExe) -ForegroundColor Gray
    Write-Host ""

    $env:PYTHONPATH = "${RootDir};${RootDir}\tests"
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    foreach ($suite in $Suites) {
        Write-Host ("--- Ejecutando: {0} ({1}) ---" -f $suite.Name, $suite.File) -ForegroundColor White
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $rawOutput = & $PythonExe -m pytest $suite.File -v --tb=short 2>&1
        $exitCode = $LASTEXITCODE
        $sw.Stop()

        $lines = $rawOutput | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
        }
        $lines | ForEach-Object { Write-Host ("  " + $_) }

        $joined = ($lines -join "`n")
        $passed = if ($joined -match "(\d+)\s+passed") { [int]$matches[1] } else { 0 }
        $failed = if ($joined -match "(\d+)\s+failed") { [int]$matches[1] } else { 0 }
        $errors = if ($joined -match "(\d+)\s+error")  { [int]$matches[1] } else { 0 }
        $failed += $errors
        if ($exitCode -ne 0 -and $failed -eq 0) { $failed = 1 }
        if ($exitCode -ne 0) { $AnyFailure = $true }

        $TotalPassed += $passed
        $TotalFailed += $failed

        $Results += [PSCustomObject]@{
            Modulo  = $suite.Name
            Estado  = if ($exitCode -eq 0) { "PASSED" } else { "FAILED" }
            Passed  = $passed
            Failed  = $failed
            Tiempo  = ("{0:N2}s" -f $sw.Elapsed.TotalSeconds)
        }
        Write-Host ""
    }
    $ErrorActionPreference = $prevPref
} else {
    $suiteFilesList = ($Suites | ForEach-Object { $_.File }) -join " "
    $reinstallFlag = if ($ReinstallDeps) { "1" } else { "0" }

    # Single-quoted Here-String evita interpolación $ de PowerShell y comillas dobles en docker.exe argv
    $bashSetup = @'
set -e
if [ $REINSTALL_DEPS = 1 ] || [ ! -x /opt/pytest-venv/bin/pytest ]; then python -m venv /opt/pytest-venv && /opt/pytest-venv/bin/pip install --root-user-action=ignore -q -r tests/requirements-test.txt; fi
set +e
overall=0
for f in $SUITE_FILES; do echo @@SUITE_START::$f; t0=$(date +%s); /opt/pytest-venv/bin/python -m pytest $f -v --tb=short; rc=$?; t1=$(date +%s); elapsed=$((t1 - t0)); echo @@SUITE_END::$f::$rc::$elapsed; if [ $rc -ne 0 ]; then overall=1; fi; done
exit $overall
'@ -replace "\r?\n", "; "

    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $rawOutput = & docker run --rm `
        -e PYTHONPATH=/workspace:/workspace/tests `
        -e REINSTALL_DEPS=$reinstallFlag `
        -e SUITE_FILES="$suiteFilesList" `
        -v "${RootDir}:/workspace" `
        -v "canchas_pytest_venv:/opt/pytest-venv" `
        -v "canchas_pip_cache:/root/.cache/pip" `
        -w /workspace `
        python:3.12-slim `
        bash -lc $bashSetup 2>&1
    $dockerExitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevPref

    $allLines = $rawOutput | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
    }

    $currentFile = $null
    $buffers = @{}
    $exitMap = @{}
    $timeMap = @{}
    $unscopedLines = @()

    foreach ($line in $allLines) {
        if ($line -match "^@@SUITE_START::(.+)$") {
            $currentFile = $matches[1].Trim()
            $buffers[$currentFile] = @()
        } elseif ($line -match "^@@SUITE_END::([^:]+)::(\d+)::(\d+)$") {
            $f = $matches[1].Trim()
            $exitMap[$f] = [int]$matches[2]
            $timeMap[$f] = ("{0}s" -f $matches[3])
            $currentFile = $null
        } elseif ($currentFile) {
            $buffers[$currentFile] += $line
        } else {
            $unscopedLines += $line
        }
    }

    if ($unscopedLines.Count -gt 0) {
        $unscopedLines | ForEach-Object { Write-Host ("  " + $_) -ForegroundColor DarkGray }
        Write-Host ""
    }

    foreach ($suite in $Suites) {
        $f = $suite.File
        Write-Host ("--- Ejecutando (Docker): {0} ({1}) ---" -f $suite.Name, $f) -ForegroundColor White
        $suiteLines = if ($buffers.ContainsKey($f)) { $buffers[$f] } else { @() }
        $suiteLines | ForEach-Object { Write-Host ("  " + $_) }

        $joined = ($suiteLines -join "`n")
        $exitCode = if ($exitMap.ContainsKey($f)) { $exitMap[$f] } else { $dockerExitCode }
        $passed = if ($joined -match "(\d+)\s+passed") { [int]$matches[1] } else { 0 }
        $failed = if ($joined -match "(\d+)\s+failed") { [int]$matches[1] } else { 0 }
        $errors = if ($joined -match "(\d+)\s+error")  { [int]$matches[1] } else { 0 }
        $failed += $errors
        if ($exitCode -ne 0 -and $failed -eq 0) { $failed = 1 }
        if ($exitCode -ne 0) { $AnyFailure = $true }

        $TotalPassed += $passed
        $TotalFailed += $failed

        $Results += [PSCustomObject]@{
            Modulo  = $suite.Name
            Estado  = if ($exitCode -eq 0) { "PASSED" } else { "FAILED" }
            Passed  = $passed
            Failed  = $failed
            Tiempo  = if ($timeMap.ContainsKey($f)) { $timeMap[$f] } else { "-" }
        }
        Write-Host ""
    }

    if ($dockerExitCode -ne 0) {
        $AnyFailure = $true
    }
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                RESUMEN DE RESULTADOS - CANCHAS POPAYAN EDA           " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
$Results | Format-Table -AutoSize | Out-String | Write-Host

Write-Host ("  TOTAL CASOS APROBADOS (PASSED) : {0}" -f $TotalPassed) -ForegroundColor Green
if ($TotalFailed -gt 0) {
    Write-Host ("  TOTAL CASOS FALLIDOS  (FAILED) : {0}" -f $TotalFailed) -ForegroundColor Red
} else {
    Write-Host ("  TOTAL CASOS FALLIDOS  (FAILED) : 0") -ForegroundColor Green
}
Write-Host "======================================================================" -ForegroundColor Cyan

if ($AnyFailure) {
    exit 1
}
exit 0

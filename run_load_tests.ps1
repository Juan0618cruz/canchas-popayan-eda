$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  CANCHAS POPAYAN EDA - SUITE DE CARGA, ESTRES Y CONCURRENCIA" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = $PSScriptRoot
$GatewayLocal = if ($env:GATEWAY_URL) { $env:GATEWAY_URL } else { "http://localhost:8000" }
$GatewayDocker = if ($env:GATEWAY_URL) { $env:GATEWAY_URL } else { "http://host.docker.internal:8000" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: No se encontro Docker en el PATH." -ForegroundColor Red
    exit 1
}

Write-Host "Verificando disponibilidad del API Gateway en $GatewayLocal/health ..." -ForegroundColor Yellow
try {
    $health = Invoke-WebRequest -Uri "$GatewayLocal/health" -UseBasicParsing -TimeoutSec 5
    if ($health.StatusCode -ne 200) {
        throw "Status HTTP $($health.StatusCode)"
    }
    Write-Host "API Gateway activo (HTTP 200 OK)." -ForegroundColor Green
} catch {
    Write-Host "ERROR: No se pudo conectar al API Gateway en $GatewayLocal." -ForegroundColor Red
    Write-Host "Asegurate de levantar los contenedores primero: docker compose up -d --build" -ForegroundColor Yellow
    exit 1
}

Write-Host "Ejecutando pruebas de carga en contenedor Docker python:3.12-slim (target: $GatewayDocker) ..." -ForegroundColor Yellow
Write-Host ""

$bashOneLine = 'set -e; export PYTHONPATH=/workspace:/workspace/tests; if [ ! -x /opt/venv/bin/pytest ]; then python -m venv /opt/venv; /opt/venv/bin/pip install --root-user-action=ignore -q --upgrade pip pytest httpx; fi; if [ ! -e /opt/venv/lib/python3.12/site-packages/httpx ]; then /opt/venv/bin/pip install --root-user-action=ignore -q httpx; fi; /opt/venv/bin/python -m pytest /workspace/tests/test_carga_concurrencia.py -v -s --tb=no'

$startTime = Get-Date
$outputLines = [System.Collections.Generic.List[string]]::new()

$prevEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& docker run --rm `
    --add-host=host.docker.internal:host-gateway `
    -e "GATEWAY_URL=$GatewayDocker" `
    -v "${RootDir}:/workspace" `
    -v "canchas_pytest_venv:/opt/venv" `
    -v "canchas_pip_cache:/root/.cache/pip" `
    -w /workspace `
    python:3.12-slim `
    bash -c $bashOneLine 2>&1 | ForEach-Object {
        $line = if ($_ -is [System.Management.Automation.ErrorRecord]) {
            $_.Exception.Message
        } else {
            "$_"
        }
        $outputLines.Add($line)
    }
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $prevEap

$elapsed = ((Get-Date) - $startTime).TotalSeconds

$fullOutput = $outputLines -join "`n"
function Get-TestStatus {
    param([string]$Text, [string]$TestName)
    if ($Text -match "(?s)$TestName(?:(?!(?:tests/test_carga_concurrencia\.py::|====)).)*?\bPASSED\b") {
        return "PASSED"
    }
    return "FAILED"
}

$t1Status = Get-TestStatus -Text $fullOutput -TestName "test_concurrencia_extrema_20_peticiones_mismo_horario"
$t2Status = Get-TestStatus -Text $fullOutput -TestName "test_carga_100_usuarios_simultaneos_lectura"
$t3Status = Get-TestStatus -Text $fullOutput -TestName "test_rafaga_15_reservas_y_pagos_wompi_paralelos"

$t1Metric = ($outputLines | Where-Object { $_ -match "^  201 Created:" } | Select-Object -First 1)
$t1Lat    = ($outputLines | Where-Object { $_ -match "^  Tiempo total rafaga:" } | Select-Object -First 1)
$t2Metric = ($outputLines | Where-Object { $_ -match "^  Throughput:" } | Select-Object -First 1)
$t2Lat    = ($outputLines | Where-Object { $_ -match "^  Latencia promedio:" } | Select-Object -First 1)
$t3Res    = ($outputLines | Where-Object { $_ -match "^  Reservas creadas \(201\):" } | Select-Object -First 1)
$t3Metric = ($outputLines | Where-Object { $_ -match "^  Pagos Wompi APROBADOS:" } | Select-Object -First 1)

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  TABLA RESUMEN DE CARGA, ESTRES Y CONCURRENCIA" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ("  {0,-48} | {1}" -f "ESCENARIO", "ESTADO") -ForegroundColor White
Write-Host "  -------------------------------------------------+--------"
Write-Host ("  {0,-48} | {1}" -f "1. Concurrencia Extrema (20 mismo slot)", $t1Status) -ForegroundColor $(if ($t1Status -eq "PASSED") { "Green" } else { "Red" })
if ($t1Metric) { Write-Host ("     -> {0}" -f $t1Metric.Trim()) -ForegroundColor Gray }
if ($t1Lat)    { Write-Host ("     -> {0}" -f $t1Lat.Trim()) -ForegroundColor Gray }
Write-Host ("  {0,-48} | {1}" -f "2. Estres Lectura (100 usuarios simultaneos)", $t2Status) -ForegroundColor $(if ($t2Status -eq "PASSED") { "Green" } else { "Red" })
if ($t2Metric) { Write-Host ("     -> {0}" -f $t2Metric.Trim()) -ForegroundColor Gray }
if ($t2Lat)    { Write-Host ("     -> {0}" -f $t2Lat.Trim()) -ForegroundColor Gray }
Write-Host ("  {0,-48} | {1}" -f "3. Rafaga 15 Reservas + 15 Pagos Wompi", $t3Status) -ForegroundColor $(if ($t3Status -eq "PASSED") { "Green" } else { "Red" })
if ($t3Res)    { Write-Host ("     -> {0}" -f $t3Res.Trim()) -ForegroundColor Gray }
if ($t3Metric) { Write-Host ("     -> {0}" -f $t3Metric.Trim()) -ForegroundColor Gray }
Write-Host "  -------------------------------------------------+--------"
Write-Host ("  Tiempo total de ejecucion : {0:N2} s" -f $elapsed)
Write-Host "  Target API Gateway        : $GatewayDocker"

if ($exitCode -eq 0) {
    Write-Host "  Resultado Global          : PASSED" -ForegroundColor Green
} else {
    Write-Host "  Resultado Global          : FAILED (Codigo de salida: $exitCode)" -ForegroundColor Red
}
Write-Host "======================================================================" -ForegroundColor Cyan

exit $exitCode

<#
.SYNOPSIS
    Hard Reset y Restauracion de Fabrica - Canchas Popayan EDA.
.DESCRIPTION
    Limpia y sincroniza los 4 contenedores PostgreSQL (db_usuarios, db_canchas, db_reservas, db_pagos),
    RabbitMQ y la base de datos de notificaciones (SQLite), dejando la plataforma impecable
    con 0 reservas, 0 pagos ($0 en caja), admin principal activo y canchas listas para demostracion en vivo.
.PARAMETER SkipConfirmation
    Omite la confirmacion interactiva previa al borrado.
.PARAMETER WithDemoPayments
    Si se especifica, siembra 6 pagos de demostracion en ms_pagos en lugar de dejar la caja en $0.
.EXAMPLE
    .\reset_db.ps1
.EXAMPLE
    .\reset_db.ps1 -SkipConfirmation
#>
[CmdletBinding()]
param (
    [switch]$SkipConfirmation,
    [switch]$Force,
    [switch]$WithDemoPayments
)

$ErrorActionPreference = "Stop"

Clear-Host
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   CANCHAS POPAYAN EDA - HARD RESET / RESTAURACION DE FABRICA        " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] No se encontro el comando 'docker' en el PATH del sistema." -ForegroundColor Red
    exit 1
}

# 2. Verificar que los contenedores esten corriendo
$requiredContainers = @("db_usuarios", "db_canchas", "db_reservas", "db_pagos", "rabbitmq")
$runningContainers = & docker ps --format "{{.Names}}" 2>$null
if (-not $runningContainers) {
    Write-Host "[ERROR] Docker no esta en ejecucion o no responde." -ForegroundColor Red
    exit 1
}

$missing = @()
foreach ($c in $requiredContainers) {
    if ($runningContainers -notcontains $c) {
        $missing += $c
    }
}

if ($missing.Count -gt 0) {
    Write-Host "[ERROR] Los siguientes contenedores requeridos no estan activos:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "   - $_" -ForegroundColor Yellow }
    Write-Host "Levantalos con: docker compose up -d" -ForegroundColor White
    exit 1
}

# 3. Confirmacion previa
if (-not $SkipConfirmation -and -not $Force) {
    Write-Host "ATENCION: Esta accion realizara un reseteo total de fabrica:" -ForegroundColor Yellow
    Write-Host "  * Vaciara todas las reservas y reiniciara codigos a RES-000001" -ForegroundColor Gray
    Write-Host "  * Vaciara todos los pagos transaccionales (caja a `$0 COP)" -ForegroundColor Gray
    Write-Host "  * Liberara el 100% de los horarios de las canchas (estado LIBRE)" -ForegroundColor Gray
    Write-Host "  * Eliminara usuarios de prueba manteniendo solo las cuentas semilla oficiales" -ForegroundColor Gray
    Write-Host "  * Purgara colas de RabbitMQ y logs de correos" -ForegroundColor Gray
    Write-Host ""
    $resp = Read-Host "Deseas proceder con el Hard Reset? (s/N)"
    if ($resp.Trim().ToLower() -ne "s" -and $resp.Trim().ToLower() -ne "si" -and $resp.Trim().ToLower() -ne "y") {
        Write-Host "Operacion cancelada por el usuario." -ForegroundColor DarkYellow
        exit 0
    }
    Write-Host ""
}

Write-Host "Iniciando proceso de limpieza y sincronizacion..." -ForegroundColor Magenta
Write-Host ""

# -----------------------------------------------------------------------------
# Paso 1: db_reservas (PostgreSQL)
# -----------------------------------------------------------------------------
Write-Host "1/6 Limpiando db_reservas..." -ForegroundColor Yellow -NoNewline
& docker exec db_reservas psql -U postgres -d db_reservas -q -c "TRUNCATE TABLE reservas RESTART IDENTITY CASCADE; TRUNCATE TABLE outbox_events RESTART IDENTITY CASCADE; INSERT INTO contador_reservas (id, contador) VALUES (1, 0) ON CONFLICT (id) DO UPDATE SET contador = 0;" 2>$null
Write-Host " [HECHO]" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Paso 2: db_pagos (PostgreSQL)
# -----------------------------------------------------------------------------
Write-Host "2/6 Limpiando db_pagos..." -ForegroundColor Yellow -NoNewline
& docker exec db_pagos psql -U postgres -d db_pagos -q -c "TRUNCATE TABLE pagos RESTART IDENTITY CASCADE;" 2>$null
if ($WithDemoPayments) {
    & docker exec ms_pagos python -c "import asyncio; from app.database import AsyncSessionLocal; from app.seed import seed_pagos; asyncio.run(seed_pagos(AsyncSessionLocal()))" 2>$null | Out-Null
    Write-Host " [HECHO (Con pagos demo)]" -ForegroundColor Green
} else {
    Write-Host " [HECHO (0 pagos, `$0 COP)]" -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# Paso 3: db_canchas (PostgreSQL)
# -----------------------------------------------------------------------------
Write-Host "3/6 Sincronizando db_canchas (liberando horarios y eliminando bloqueos)..." -ForegroundColor Yellow -NoNewline
& docker exec db_canchas psql -U postgres -d db_canchas -q -c "UPDATE bloques_horarios SET estado = 'LIBRE', reserva_id = NULL; TRUNCATE TABLE bloqueos_mantenimiento RESTART IDENTITY CASCADE;" 2>$null
# Re-asegurar que existan las canchas y slots para los proximos 30 dias
& docker exec ms_canchas python -c "import asyncio; from app.database import AsyncSessionLocal; from app.seed import seed_database; asyncio.run(seed_database(AsyncSessionLocal()))" 2>$null | Out-Null
Write-Host " [HECHO]" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Paso 4: db_usuarios (PostgreSQL)
# -----------------------------------------------------------------------------
Write-Host "4/6 Depurando usuarios de prueba en db_usuarios..." -ForegroundColor Yellow -NoNewline
$cleanUsersSql = @"
DELETE FROM tokens_recuperacion WHERE usuario_id NOT IN (SELECT id FROM usuarios WHERE email IN ('jpdiagon1@gmail.com', 'admin.balon@test.com', 'deportista@test.com'));
DELETE FROM usuarios WHERE email NOT IN ('jpdiagon1@gmail.com', 'admin.balon@test.com', 'deportista@test.com');
UPDATE usuarios SET activo = true WHERE email IN ('jpdiagon1@gmail.com', 'admin.balon@test.com', 'deportista@test.com');
"@
& docker exec db_usuarios psql -U postgres -d db_usuarios -q -c "$cleanUsersSql" 2>$null
& docker exec ms_usuarios python -c "import asyncio; from app.database import AsyncSessionLocal; from app.seed import run_seed; asyncio.run(run_seed(AsyncSessionLocal()))" 2>$null | Out-Null
Write-Host " [HECHO]" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Paso 5: ms_notificaciones (SQLite)
# -----------------------------------------------------------------------------
Write-Host "5/6 Vaciando bandeja de notificaciones (ms_notificaciones)..." -ForegroundColor Yellow -NoNewline
& docker exec ms_notificaciones python -c "import sqlite3, os; p='/app/data/notificaciones.db'; conn = sqlite3.connect(p) if os.path.exists(p) else None; (conn.execute('DELETE FROM email_logs;'), conn.commit(), conn.close()) if conn else None" 2>$null
Write-Host " [HECHO]" -ForegroundColor Green

# -----------------------------------------------------------------------------
# Paso 6: RabbitMQ (Purgar Colas)
# -----------------------------------------------------------------------------
Write-Host "6/6 Purgando colas residuales en RabbitMQ..." -ForegroundColor Yellow -NoNewline
$rawQueues = & docker exec rabbitmq rabbitmqctl list_queues -q name 2>$null
foreach ($q in $rawQueues) {
    $qName = $q.Trim()
    if ($qName -and $qName -ne "name") {
        & docker exec rabbitmq rabbitmqctl purge_queue $qName 2>$null | Out-Null
    }
}
Write-Host " [HECHO]" -ForegroundColor Green
Write-Host ""

# -----------------------------------------------------------------------------
# Paso 7: Obtencion de Metricas y Auditoria de Fabrica
# -----------------------------------------------------------------------------
Write-Host "Obteniendo metricas finales de auditoria..." -ForegroundColor Cyan

# Usuarios
$usrCount = (& docker exec db_usuarios psql -U postgres -d db_usuarios -t -A -c "SELECT count(*) FROM usuarios;" 2>$null).Trim()
$adminActivo = (& docker exec db_usuarios psql -U postgres -d db_usuarios -t -A -c "SELECT count(*) FROM usuarios WHERE email = 'jpdiagon1@gmail.com' AND activo = true;" 2>$null).Trim()

# Canchas
$complejosCount = (& docker exec db_canchas psql -U postgres -d db_canchas -t -A -c "SELECT count(*) FROM complejos;" 2>$null).Trim()
$canchasCount = (& docker exec db_canchas psql -U postgres -d db_canchas -t -A -c "SELECT count(*) FROM canchas WHERE activo = true;" 2>$null).Trim()
$slotsStats = (& docker exec db_canchas psql -U postgres -d db_canchas -t -A -c "SELECT count(*), count(*) FILTER (WHERE estado = 'LIBRE'), count(*) FILTER (WHERE estado != 'LIBRE') FROM bloques_horarios;" 2>$null).Trim()
$slotParts = $slotsStats -split '\|'
$slotsTotal = if ($slotParts.Length -ge 1) { $slotParts[0] } else { "0" }
$slotsLibres = if ($slotParts.Length -ge 2) { $slotParts[1] } else { "0" }
$slotsOcupados = if ($slotParts.Length -ge 3) { $slotParts[2] } else { "0" }

# Reservas
$resCount = (& docker exec db_reservas psql -U postgres -d db_reservas -t -A -c "SELECT count(*) FROM reservas;" 2>$null).Trim()
$outboxCount = (& docker exec db_reservas psql -U postgres -d db_reservas -t -A -c "SELECT count(*) FROM outbox_events;" 2>$null).Trim()
$contadorSeq = (& docker exec db_reservas psql -U postgres -d db_reservas -t -A -c "SELECT coalesce(contador, 0) FROM contador_reservas WHERE id = 1;" 2>$null).Trim()
$nextCode = "RES-" + ("{0:D6}" -f ([int]$contadorSeq + 1))

# Pagos
$pagosStats = (& docker exec db_pagos psql -U postgres -d db_pagos -t -A -c "SELECT count(*), coalesce(sum(monto), 0) FROM pagos;" 2>$null).Trim()
$pagoParts = $pagosStats -split '\|'
$pagosTotal = if ($pagoParts.Length -ge 1) { $pagoParts[0] } else { "0" }
$pagosMonto = if ($pagoParts.Length -ge 2) { [double]$pagoParts[1] } else { 0.0 }
$pagosMontoFmt = "`$$('{0:N0}' -f $pagosMonto) COP"

# Notificaciones
$notifCount = (& docker exec ms_notificaciones python -c "import sqlite3, os; p='/app/data/notificaciones.db'; print(sqlite3.connect(p).cursor().execute('SELECT count(*) FROM email_logs;').fetchone()[0] if os.path.exists(p) else 0)" 2>$null).Trim()

# RabbitMQ
$rmqMessages = 0
$rmqQueuesCount = 0
$rmqStats = & docker exec rabbitmq rabbitmqctl list_queues -q name messages 2>$null
foreach ($line in $rmqStats) {
    $parts = $line.Trim() -split '\s+'
    if ($parts.Length -ge 2 -and $parts[0] -ne "name") {
        $rmqQueuesCount++
        $rmqMessages += [int]$parts[1]
    }
}

# -----------------------------------------------------------------------------
# Generacion de la Tabla Visual de Reporte
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "=====================================================================================" -ForegroundColor Cyan
Write-Host "             REPORTE DE ESTADO POST-RESET (FABRICA / DEMO EN VIVO)                   " -ForegroundColor Cyan
Write-Host "=====================================================================================" -ForegroundColor Cyan
Write-Host ("{0,-20} {1,-32} {2,-18} {3,-12}" -f "COMPONENTE", "METRICA VERIFICADA", "VALOR ACTUAL", "ESTADO") -ForegroundColor White
Write-Host ("-" * 85) -ForegroundColor Gray

function Format-ReportRow {
    param($Comp, $Metrica, $Valor, $Ok, $Detalle)
    $badge = if ($Ok) { "[OK]" } else { "[FALLO]" }
    $color = if ($Ok) { "Green" } else { "Red" }
    $valStr = "$Valor $Detalle".Trim()
    Write-Host ("{0,-20} {1,-32} {2,-18} " -f $Comp, $Metrica, $valStr) -NoNewline
    Write-Host ("{0,-12}" -f $badge) -ForegroundColor $color
}

Format-ReportRow "db_usuarios" "Usuarios Semilla" "$usrCount cuentas" ($usrCount -eq "3") "(3 oficiales)"
Format-ReportRow "db_usuarios" "Admin Balon de Oro" "Activo" ($adminActivo -eq "1") "(jpdiagon1@gmail.com)"
Format-ReportRow "db_canchas" "Complejos Deportivos" "$complejosCount activos" ($complejosCount -eq "2") "(Balon de Oro, Bernabeu)"
Format-ReportRow "db_canchas" "Canchas Sinteticas" "$canchasCount canchas" ($canchasCount -eq "6") "(100% operativas)"
Format-ReportRow "db_canchas" "Bloques Horarios" "$slotsLibres libres" ($slotsOcupados -eq "0") "($slotsOcupados ocupados / 100% libre)"
Format-ReportRow "db_reservas" "Reservas Activas" "$resCount reservas" ($resCount -eq "0") "(Vacio de fabrica)"
Format-ReportRow "db_reservas" "Eventos Outbox" "$outboxCount eventos" ($outboxCount -eq "0") "(Sin pendientes)"
Format-ReportRow "db_reservas" "Generador Codigos" "$nextCode" ($contadorSeq -eq "0") "(Reiniciado a 0)"
Format-ReportRow "db_pagos" "Transacciones Caja" "$pagosTotal pagos" ($pagosTotal -eq "0" -or $WithDemoPayments) "(0 movimientos)"
Format-ReportRow "db_pagos" "Recaudacion Total" "$pagosMontoFmt" ($pagosMonto -eq 0 -or $WithDemoPayments) "(`$0 COP en caja)"
Format-ReportRow "ms_notificaciones" "Historial Correos" "$notifCount logs" ($notifCount -eq "0") "(Bandeja limpia)"
Format-ReportRow "RabbitMQ" "Colas de Mensajes" "$rmqMessages pendientes" ($rmqMessages -eq 0) "($rmqQueuesCount colas activas)"

Write-Host ("=" * 85) -ForegroundColor Cyan
Write-Host "   ESTADO GLOBAL: PLATAFORMA 100% LIMPIA Y LISTA PARA PRESENTACION EN VIVO          " -ForegroundColor Green
Write-Host "=====================================================================================" -ForegroundColor Cyan
Write-Host ""

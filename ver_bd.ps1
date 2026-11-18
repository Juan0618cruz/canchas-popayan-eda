<#
.SYNOPSIS
    Inspector de bases de datos PostgreSQL — Canchas Popayán EDA.
.DESCRIPTION
    Consulta mediante `docker exec` las 4 bases de datos independientes del proyecto
    (`db_usuarios`, `db_canchas`, `db_reservas` y `db_pagos`) usando los nombres
    exactos de tablas y columnas definidos en `ms_*/app/models/` para mostrar
    usuarios, canchas, reservas y pagos (incluyendo Wompi) de forma ordenada.
#>

param(
    [int]$Limit = 30
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "         CANCHAS POPAYAN EDA - CONSULTA DE BASES DE DATOS (POSTGRESQL)          " -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ("Fecha de consulta : {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray
Write-Host ""

function Invoke-DbQuery {
    param(
        [string]$Titulo,
        [string]$Container,
        [string]$Database,
        [string]$Sql
    )

    Write-Host ("--- {0} ({1} / {2}) ---" -f $Titulo, $Container, $Database) -ForegroundColor Yellow

    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    # Intentar primero contra la BD configurada en docker-compose (y fallback a -d postgres)
    $raw = & docker exec $Container psql -U postgres -d $Database -P "pager=off" -P "border=2" -c $Sql 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0 -and $Database -ne "postgres") {
        $raw = & docker exec $Container psql -U postgres -d postgres -P "pager=off" -P "border=2" -c $Sql 2>&1
        $code = $LASTEXITCODE
    }

    $ErrorActionPreference = $prevPref

    $lines = $raw | ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { "$_" }
    }

    if ($code -ne 0) {
        Write-Host ("  [ERROR] No se pudo consultar {0}:" -f $Container) -ForegroundColor Red
        $lines | ForEach-Object { Write-Host ("    " + $_) -ForegroundColor Red }
    } else {
        $lines | ForEach-Object { Write-Host ("  " + $_) }
    }
    Write-Host ""
}

$sqlUsuarios = @"
SELECT id,
       nombre,
       email,
       COALESCE(telefono, '-') AS telefono,
       rol,
       activo,
       to_char(created_at, 'YYYY-MM-DD HH24:MI') AS creado
FROM usuarios
ORDER BY created_at DESC
LIMIT $Limit;
"@

$sqlCanchas = @"
SELECT c.id,
       COALESCE(cp.nombre, '-') AS complejo,
       c.nombre AS cancha,
       c.tipo,
       c.tarifa_por_hora,
       c.activo,
       to_char(c.hora_apertura, 'HH24:MI') || '-' || to_char(c.hora_cierre, 'HH24:MI') AS horario
FROM canchas c
LEFT JOIN complejos cp ON cp.id = c.complejo_id
ORDER BY cp.nombre, c.nombre
LIMIT $Limit;
"@

$sqlReservas = @"
SELECT codigo_uid,
       COALESCE(nombre_cliente, 'Sin nombre') AS cliente,
       fecha,
       to_char(hora_inicio, 'HH24:MI') || '-' || to_char(hora_fin, 'HH24:MI') AS horario,
       monto,
       estado,
       usuario_id
FROM reservas
ORDER BY fecha DESC, hora_inicio DESC
LIMIT $Limit;
"@

$sqlPagos = @"
SELECT COALESCE(referencia_externa, '-') AS referencia,
       metodo,
       estado,
       monto,
       reserva_id,
       to_char(created_at, 'YYYY-MM-DD HH24:MI') AS fecha_pago,
       LEFT(COALESCE(observaciones, ''), 45) AS observaciones
FROM pagos
ORDER BY created_at DESC
LIMIT $Limit;
"@

Invoke-DbQuery -Titulo "1. USUARIOS REGISTRADOS"        -Container "db_usuarios" -Database "db_usuarios" -Sql $sqlUsuarios
Invoke-DbQuery -Titulo "2. COMPLEJOS Y CANCHAS"         -Container "db_canchas"  -Database "db_canchas"  -Sql $sqlCanchas
Invoke-DbQuery -Titulo "3. RESERVAS"                    -Container "db_reservas" -Database "db_reservas" -Sql $sqlReservas
Invoke-DbQuery -Titulo "4. PAGOS (WOMPI Y PRESENCIAL)"  -Container "db_pagos"    -Database "db_pagos"    -Sql $sqlPagos

Write-Host "================================================================================" -ForegroundColor Cyan

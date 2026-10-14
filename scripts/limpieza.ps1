# Limpieza de ficheros no utilizados en EntrevistasExpress (version Windows / PowerShell).
# Ejecutar desde la RAIZ del repo, en el portatil nuevo, con el repo ya clonado.
#
# Cada bloque esta verificado por mi con grep contra el codigo real: ninguno de
# estos ficheros esta importado, extendido (Jinja) ni enlazado desde ningun sitio.
#
# Requiere: Git for Windows (git.exe en el PATH). No requiere Git Bash ni WSL:
# "git rm" interpreta las rutas con '/' igual en Windows que en Linux, asi que
# las rutas no se han tocado respecto a la version .sh.
#
# Equivalente a "set -euo pipefail": paramos en el primer error en vez de
# seguir borrando a ciegas.
$ErrorActionPreference = "Stop"

function Remove-GitFiles {
    param(
        [Parameter(Mandatory = $true)][string[]]$Paths
    )
    & git rm @Paths
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git rm fallo (codigo $LASTEXITCODE) con: $($Paths -join ', ')"
        exit $LASTEXITCODE
    }
}

function Remove-GitFilesRecursive {
    param(
        [Parameter(Mandatory = $true)][string]$Path
    )
    & git rm -r $Path
    if ($LASTEXITCODE -ne 0) {
        Write-Error "git rm -r fallo (codigo $LASTEXITCODE) con: $Path"
        exit $LASTEXITCODE
    }
}

Write-Host "== Duplicados/backups de app.py =="
Remove-GitFiles -Paths @("app_v1.py", "app_backup.py")

Write-Host "== Snippets ya integrados en app.py =="
Remove-GitFilesRecursive -Path "ext_codes/"

Write-Host "== Plantillas Jinja huerfanas (nadie hace {% extends %} de ellas) =="
Remove-GitFiles -Paths @(
    "templates/base_backup.html",
    "templates/base_alerts.html",
    "templates/reservas_og.html"
)

Write-Host "== CSS/JS que ninguna plantilla carga =="
Remove-GitFiles -Paths @(
    "static/css/admin.css",
    "static/css/login.css",
    "static/css/mis-reservas.css",
    "static/js/script.js"
)

Write-Host "== SQL de migracion ya aplicada (sus ALTER TABLE ya estan en el esquema actual) =="
Remove-GitFiles -Paths @(
    "sql/setup.sql",
    "sql/migracion_roles.sql",
    "sql/actualizacion_reserva_admin.sql"
)

# ---------------------------------------------------------------------------
# Lo siguiente lo he dejado comentado porque es una decision tuya, no un hecho
# verificable por grep. Descomenta lo que quieras aplicar.
# ---------------------------------------------------------------------------

# asignar_candidatos.py: script suelto que no importa app.py y que apunta a
# OTRA base de datos (reservas_db) con credenciales propias en el codigo.
# Remove-GitFiles -Paths @("asignar_candidatos.py")

# entrevistas_api.yml: especificacion OpenAPI que no usa ni sirve el codigo
# actual (puede ser documentacion que quieras conservar o actualizar).
# Remove-GitFiles -Paths @("entrevistas_api.yml")

# Excel de muestra en la raiz (datos de candidatos reales/de prueba, ~140 KB
# cada uno). Solo los usaba ext_codes/preprocesar_excel.py, ya eliminado.
# Remove-GitFiles -Paths @("calificaciones.xlsx", "calificaciones_1.xlsx", "candidatos_modelo_2.xlsx")

# Logo en base64: la app no lo usa en ningun sitio (0 referencias a "base64"
# en app.py). Si no vas a retomar el envio del logo embebido en emails:
# Remove-GitFiles -Paths @("static/images/logoEuefHorizontal_base64.txt")
# El .png y convertir_base64.py los dejo fuera de este script: son la
# herramienta y su entrada, no un resultado muerto.

Write-Host ""
Write-Host "Hecho. Revisa 'git status' y haz commit."

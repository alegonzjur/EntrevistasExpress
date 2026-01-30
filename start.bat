@echo off
REM ================================================================
REM Script de inicio rápido para Booking System
REM Ejecutar: start.bat
REM ================================================================

echo ========================================
echo   BOOKING SYSTEM - INICIANDO
echo ========================================
echo.

REM Verificar si existe el entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: No se encuentra el entorno virtual
    echo Por favor ejecuta primero: python -m venv venv
    echo.
    pause
    exit /b 1
)

REM Activar entorno virtual
echo [1/3] Activando entorno virtual...
call venv\Scripts\activate.bat

REM Verificar conexión a base de datos
echo [2/3] Verificando conexión a base de datos...
python -c "from app import db; db.engine.connect()" 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: No se puede conectar a la base de datos
    echo Verifica:
    echo   - PostgreSQL está ejecutándose
    echo   - Credenciales en config.py son correctas
    echo   - La base de datos existe
    echo.
    pause
    exit /b 1
)
echo    Base de datos OK

REM Iniciar servidor con Waitress
echo [3/3] Iniciando servidor de producción...
echo.
echo ========================================
echo   SERVIDOR LISTO
echo   URL: http://localhost:5000
echo   Presiona CTRL+C para detener
echo ========================================
echo.

python serve.py

pause
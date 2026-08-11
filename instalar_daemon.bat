@echo off
chcp 65001 > NUL
title Instalador del Daemon de Cookies de Colsubsidio

echo ==============================================================
echo   Instalador de Tarea Programada - Daemon Colsubsidio
echo ==============================================================
echo.
echo Este script registrará la tarea programada 'ColsubsidioCookieSync'
echo en Windows para sincronizar automáticamente las cookies de sesión
echo a GitHub Secrets en segundo plano cada 4 horas y al iniciar sesión.
echo.

set SCRIPT_DIR=%~dp0
set VBS_PATH=%SCRIPT_DIR%run_daemon_silent.vbs

if not exist "%VBS_PATH%" (
    echo [ERROR] No se encontró el archivo 'run_daemon_silent.vbs' en %SCRIPT_DIR%
    pause
    exit /b 1
)

echo Creando tarea programada 'ColsubsidioCookieSync'...
schtasks /create /tn "ColsubsidioCookieSync" /tr "wscript.exe \"%VBS_PATH%\"" /sc HOURLY /mo 4 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================================
    echo [EXITO] La tarea programada ha sido registrada correctamente.
    echo El daemon funcionará en segundo plano de forma 100%% invisible.
    echo ==============================================================
) else (
    echo.
    echo [WARNING] No se pudo crear la tarea programada automáticamente.
    echo Intenta ejecutar este archivo haciendo clic derecho -> 'Ejecutar como Administrador'.
)

echo.
pause

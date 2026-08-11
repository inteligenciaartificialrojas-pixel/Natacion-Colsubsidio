@echo off
cd /d "%~dp0"
title Revisor de Natacion - Bucle Local Auto-Sanable
echo =========================================================
echo Iniciando Revisor de Natacion Colsubsidio...
echo (Este script actualizara tus cookies de forma automatica)
echo =========================================================
echo.

:: Detectar ejecutable de Python del sistema o launcher
set "PYTHON_EXE=python"
where py >nul 2>&1
if %ERRORLEVEL% equ 0 set "PYTHON_EXE=py"

:: Extraer cookies antes de iniciar
"%PYTHON_EXE%" "%~dp0code\get_cookies.py"
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo.
echo Iniciando monitor continuo (revisara cada 5 minutos)...
echo Presiona Ctrl+C para detener el proceso.
echo.

"%PYTHON_EXE%" "%~dp0code\main.py"
pause

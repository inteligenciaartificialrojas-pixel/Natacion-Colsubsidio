@echo off
cd /d "%~dp0"
title Extractor de Cookies - Revisor de Natación Colsubsidio
echo =========================================================
echo Iniciando extracción automatizada de cookies...
echo =========================================================
echo.

:: Detectar ejecutable de Python del sistema o launcher
set "PYTHON_EXE=python"
where py >nul 2>&1
if %ERRORLEVEL% equ 0 set "PYTHON_EXE=py"

"%PYTHON_EXE%" "%~dp0code\get_cookies.py"

echo.
echo =========================================================
echo Proceso finalizado.
echo =========================================================
pause

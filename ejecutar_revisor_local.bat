@echo off
title Revisor de Natacion - Bucle Local Auto-Sanable
echo =========================================================
echo Iniciando Revisor de Natacion Colsubsidio...
echo (Este script actualizara tus cookies de forma automatica)
echo =========================================================
echo.

set "PYTHON_EXE=C:\Users\andre\AppData\Local\Python\bin\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

:: Extraer cookies antes de iniciar
"%PYTHON_EXE%" "%~dp0code\get_cookies.py"

echo.
echo Iniciando monitor continuo (revisara cada 5 minutos)...
echo Presiona Ctrl+C para detener el proceso.
echo.

"%PYTHON_EXE%" "%~dp0code\main.py"
pause

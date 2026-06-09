@echo off
title Extractor de Cookies - Revisor de Natación Colsubsidio
echo =========================================================
echo Iniciando extracción automatizada de cookies...
echo =========================================================
echo.

:: Detectar ruta del python del usuario
set "PYTHON_EXE=C:\Users\andre\AppData\Local\Python\bin\python.exe"

if not exist "%PYTHON_EXE%" (
    :: Intentar con python normal si no existe la ruta específica
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%~dp0code\get_cookies.py"

echo.
echo =========================================================
echo Proceso finalizado.
echo =========================================================
pause

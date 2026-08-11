"""Pruebas unitarias e integración para el Hito M4 (Compatibilidad CI/CD y Batch Local)."""
from __future__ import annotations

import os
from pathlib import Path
import pytest


def test_requirements_contains_playwright() -> None:
    """Verifica que code/requirements.txt contenga la dependencia playwright>=1.40.0."""
    req_path = Path(__file__).parent.parent.parent / "code" / "requirements.txt"
    assert req_path.exists(), "code/requirements.txt debe existir."
    content = req_path.read_text(encoding="utf-8")
    assert "playwright>=1.40.0" in content, "code/requirements.txt debe incluir 'playwright>=1.40.0'."


def test_env_example_contains_credentials_placeholders() -> None:
    """Verifica que .env.example contenga los placeholders COLSUBSIDIO_USER y COLSUBSIDIO_PASS."""
    env_ex_path = Path(__file__).parent.parent.parent / ".env.example"
    assert env_ex_path.exists(), ".env.example debe existir."
    content = env_ex_path.read_text(encoding="utf-8")
    assert "COLSUBSIDIO_USER=" in content, ".env.example debe contener COLSUBSIDIO_USER."
    assert "COLSUBSIDIO_PASS=" in content, ".env.example debe contener COLSUBSIDIO_PASS."


def test_github_workflow_check_yml_configuration() -> None:
    """Verifica la configuración del workflow de GitHub Actions en .github/workflows/check.yml."""
    workflow_path = Path(__file__).parent.parent.parent / ".github" / "workflows" / "check.yml"
    assert workflow_path.exists(), ".github/workflows/check.yml debe existir."
    content = workflow_path.read_text(encoding="utf-8")

    # 1. Instalación de dependencias de Playwright Chromium
    assert "python -m playwright install --with-deps chromium" in content, (
        "check.yml debe incluir la instalación de Playwright Chromium con dependencias."
    )

    # 2. Caché de binarios de Playwright mediante actions/cache
    assert "actions/cache" in content, "check.yml debe usar actions/cache para binarios de Playwright."
    assert "~/.cache/ms-playwright" in content, "check.yml debe especificar la ruta de caché ~/.cache/ms-playwright."

    # 3. Transmisión de secretos COLSUBSIDIO_USER y COLSUBSIDIO_PASS
    assert "COLSUBSIDIO_USER: ${{ secrets.COLSUBSIDIO_USER }}" in content, (
        "check.yml debe pasar el secreto COLSUBSIDIO_USER."
    )
    assert "COLSUBSIDIO_PASS: ${{ secrets.COLSUBSIDIO_PASS }}" in content, (
        "check.yml debe pasar el secreto COLSUBSIDIO_PASS."
    )

    # 4. Ejecución del comando python code/main.py --once
    assert "python code/main.py --once" in content, (
        "check.yml debe ejecutar python code/main.py --once."
    )

    # 5. Verificación de versiones válidas de GitHub Actions (sin tags obsoletos o inexistentes v5/v6)
    assert "actions/checkout@v4" in content, "check.yml debe usar actions/checkout@v4."
    assert "actions/setup-python@v5" in content, "check.yml debe usar actions/setup-python@v5."
    assert "@v6" not in content, "check.yml no debe contener tags inexistentes @v6."
    assert "checkout@v5" not in content, "check.yml no debe usar checkout@v5."
    assert "setup-python@v6" not in content, "check.yml no debe usar setup-python@v6."
    assert "restore@v5" not in content, "check.yml no debe usar cache/restore@v5."
    assert "save@v5" not in content, "check.yml no debe usar cache/save@v5."


def test_local_batch_runner_scripts() -> None:
    """Verifica la integridad de los scripts batch de ejecución local."""
    base_dir = Path(__file__).parent.parent.parent
    actualizar_bat = base_dir / "actualizar_cookies.bat"
    ejecutar_bat = base_dir / "ejecutar_revisor_local.bat"

    assert actualizar_bat.exists(), "actualizar_cookies.bat debe existir."
    assert ejecutar_bat.exists(), "ejecutar_revisor_local.bat debe existir."

    act_content = actualizar_bat.read_text(encoding="utf-8", errors="ignore")
    eje_content = ejecutar_bat.read_text(encoding="utf-8", errors="ignore")

    # Verificar navegación al directorio de trabajo en ambos scripts
    assert 'cd /d "%~dp0"' in act_content, "actualizar_cookies.bat debe contener 'cd /d \"%~dp0\"'."
    assert 'cd /d "%~dp0"' in eje_content, "ejecutar_revisor_local.bat debe contener 'cd /d \"%~dp0\"'."

    # Verificar que invoquen get_cookies.py y main.py respectivamente
    assert "get_cookies.py" in act_content, "actualizar_cookies.bat debe ejecutar get_cookies.py."
    assert "get_cookies.py" in eje_content, "ejecutar_revisor_local.bat debe ejecutar get_cookies.py."
    assert "main.py" in eje_content, "ejecutar_revisor_local.bat debe ejecutar main.py."

    # Verificar verificación de código de error tras get_cookies.py en ejecutar_revisor_local.bat
    assert "if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%" in eje_content, (
        "ejecutar_revisor_local.bat debe abortar si get_cookies.py falla."
    )

    # Verificar detección de executable de Python y ausencia de rutas de usuario hardcoded
    assert "PYTHON_EXE" in act_content
    assert "PYTHON_EXE" in eje_content
    assert "C:\\Users\\" not in act_content, "actualizar_cookies.bat no debe tener rutas de usuario hardcoded."
    assert "C:\\Users\\" not in eje_content, "ejecutar_revisor_local.bat no debe tener rutas de usuario hardcoded."


def test_get_cookies_cookie_logging_safety() -> None:
    """Verifica que code/get_cookies.py no imprima valores crudos de cookies sensibles."""
    gc_path = Path(__file__).parent.parent.parent / "code" / "get_cookies.py"
    assert gc_path.exists(), "code/get_cookies.py debe existir."
    content = gc_path.read_text(encoding="utf-8")

    # Verificar que no se impriman los valores crudos de las cookies en stdout/logging
    assert "print(f\"sistema: {cookies['sistema']}\")" not in content, (
        "code/get_cookies.py no debe imprimir el valor sensible de la cookie sistema."
    )
    assert "print(f\"Csrf-Token: {cookies['Csrf-Token']}\")" not in content, (
        "code/get_cookies.py no debe imprimir el valor sensible de la cookie Csrf-Token."
    )
    assert "sistema cookie captured" in content, (
        "code/get_cookies.py debe registrar la presencia/longitud de la cookie sistema de forma segura."
    )
    assert "Csrf-Token cookie captured" in content, (
        "code/get_cookies.py debe registrar la presencia/longitud de la cookie Csrf-Token de forma segura."
    )

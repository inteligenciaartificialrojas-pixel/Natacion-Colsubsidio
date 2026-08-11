"""Script de verificación adversaria empírica para el Hito M4.
Ejecuta validaciones profundas de requirements.txt, .env.example, workflows de CI/CD y tests de arnes.
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path

def test_requirements_txt_deep() -> dict:
    """Verifica sintaxis, parseo PEP 440/508 y completitud de dependencias en code/requirements.txt."""
    req_file = Path("code/requirements.txt")
    results = {
        "file_exists": req_file.exists(),
        "lines": [],
        "parsed_packages": {},
        "missing_imports": [],
        "errors": []
    }
    
    if not req_file.exists():
        results["errors"].append("code/requirements.txt no existe.")
        return results

    content = req_file.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
    results["lines"] = lines

    # Expresión regular PEP 508 simplificada para package_name >= version
    req_pattern = re.compile(r"^([a-zA-Z0-9_\-]+)\s*([<>=!~]+)\s*([0-9a-zA-Z\.\-]+)$")
    
    for line in lines:
        match = req_pattern.match(line)
        if match:
            pkg, op, ver = match.groups()
            results["parsed_packages"][pkg.lower()] = {"op": op, "ver": ver, "raw": line}
        else:
            results["errors"].append(f"Línea de requerimiento inválida en requirements.txt: '{line}'")

    # Verificar paquetes requeridos
    expected_pkgs = ["requests", "pytest", "playwright"]
    for expected in expected_pkgs:
        if expected not in results["parsed_packages"]:
            results["errors"].append(f"Paquete esperado '{expected}' no encontrado en requirements.txt")

    # Escanear importaciones en la carpeta code/
    code_dir = Path("code")
    imported_third_party = set()
    std_libs = {
        "os", "sys", "json", "base64", "sqlite3", "shutil", "tempfile", "ctypes", 
        "wintypes", "logging", "time", "datetime", "re", "pathlib", "typing", "subprocess"
    }

    if code_dir.exists():
        import_pattern = re.compile(r"^\s*(?:import|from)\s+([a-zA-Z0-9_\-]+)")
        for py_file in code_dir.glob("*.py"):
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                m = import_pattern.match(line)
                if m:
                    mod = m.group(1).split(".")[0]
                    if mod not in std_libs and mod not in ["config", "scraper", "notifier", "get_cookies", "main"]:
                        imported_third_party.add(mod)

    results["detected_third_party_imports"] = sorted(list(imported_third_party))
    
    # Cryptography es opcional con try/except
    for imp in imported_third_party:
        if imp not in results["parsed_packages"] and imp != "cryptography":
            results["missing_imports"].append(imp)

    return results

def test_env_example_deep() -> dict:
    """Verifica .env.example y compatibilidad de parseo entre config.py custom y dotenv."""
    env_ex_file = Path(".env.example")
    results = {
        "file_exists": env_ex_file.exists(),
        "keys_custom_parser": {},
        "keys_dotenv_style": {},
        "discrepancies": [],
        "missing_config_keys": [],
        "errors": []
    }

    if not env_ex_file.exists():
        results["errors"].append(".env.example no existe.")
        return results

    content = env_ex_file.read_text(encoding="utf-8")
    
    # 1. Simulación de custom parser de config.py
    custom_parsed = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("=", 1)
        if len(parts) == 2:
            key = parts[0].strip()
            val = parts[1].strip().strip('"').strip("'")
            custom_parsed[key] = val

    results["keys_custom_parser"] = custom_parsed

    # 2. Simulación de parser dotenv estricto (PEP / dotenv specification)
    dotenv_parsed = {}
    dotenv_pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
    for line in content.splitlines():
        line_s = line.strip()
        if not line_s or line_s.startswith("#"):
            continue
        m = dotenv_pattern.match(line)
        if m:
            k, v = m.groups()
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            dotenv_parsed[k] = v

    results["keys_dotenv_style"] = dotenv_parsed

    # Comparar discrepancias
    if custom_parsed != dotenv_parsed:
        results["discrepancies"].append(
            f"Discrepancia entre custom parser ({custom_parsed}) y dotenv ({dotenv_parsed})"
        )

    # Verificar claves esperadas en config.py
    required_config_keys = [
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "COLSUBSIDIO_USER",
        "COLSUBSIDIO_PASS",
        "COLSUBSIDIO_SISTEMA_COOKIE",
        "COLSUBSIDIO_CSRF_TOKEN"
    ]
    for req_k in required_config_keys:
        if req_k not in custom_parsed:
            results["missing_config_keys"].append(req_k)

    return results

def test_github_workflow_and_batch_scripts() -> dict:
    """Verifica .github/workflows/check.yml y scripts batch."""
    results = {
        "workflow_exists": False,
        "action_version_warnings": [],
        "workflow_checks": {},
        "batch_checks": {},
        "errors": []
    }

    wf_file = Path(".github/workflows/check.yml")
    results["workflow_exists"] = wf_file.exists()
    if wf_file.exists():
        content = wf_file.read_text(encoding="utf-8")
        
        # Validar etiquetas de versión de GitHub Actions
        # actions/checkout@v5 -> actualmente v4 es el release oficial estable. v5 puede ser inexistente/unreleased.
        # actions/setup-python@v6 -> actualmente v5 es el release oficial estable.
        # actions/cache/restore@v5 -> actualmente v4 es el release oficial estable.
        # actions/cache/save@v5 -> actualmente v4 es el release oficial estable.
        if "actions/checkout@v5" in content:
            results["action_version_warnings"].append(
                "actions/checkout@v5 usa una etiqueta de versión futura/inexistente; la versión estable actual es actions/checkout@v4."
            )
        if "actions/setup-python@v6" in content:
            results["action_version_warnings"].append(
                "actions/setup-python@v6 usa una etiqueta de versión futura/inexistente; la versión estable actual es actions/setup-python@v5."
            )
        if "actions/cache/restore@v5" in content:
            results["action_version_warnings"].append(
                "actions/cache/restore@v5 usa una etiqueta de versión futura/inexistente; la versión estable actual es actions/cache/restore@v4."
            )
        if "actions/cache/save@v5" in content:
            results["action_version_warnings"].append(
                "actions/cache/save@v5 usa una etiqueta de versión futura/inexistente; la versión estable actual es actions/cache/save@v4."
            )

        results["workflow_checks"] = {
            "has_playwright_install": "python -m playwright install --with-deps chromium" in content,
            "has_playwright_cache": "actions/cache" in content and "~/.cache/ms-playwright" in content,
            "has_secrets_user": "COLSUBSIDIO_USER: ${{ secrets.COLSUBSIDIO_USER }}" in content,
            "has_secrets_pass": "COLSUBSIDIO_PASS: ${{ secrets.COLSUBSIDIO_PASS }}" in content,
            "has_run_once": "python code/main.py --once" in content,
            "has_cron": "cron:" in content,
        }

    # Scripts batch
    act_bat = Path("actualizar_cookies.bat")
    eje_bat = Path("ejecutar_revisor_local.bat")
    results["batch_checks"] = {
        "actualizar_cookies_exists": act_bat.exists(),
        "ejecutar_revisor_exists": eje_bat.exists(),
        "actualizar_has_python_exe": "PYTHON_EXE" in act_bat.read_text(encoding="utf-8", errors="ignore") if act_bat.exists() else False,
        "ejecutar_has_python_exe": "PYTHON_EXE" in eje_bat.read_text(encoding="utf-8", errors="ignore") if eje_bat.exists() else False,
    }

    return results

if __name__ == "__main__":
    print("=== ADVERSARIAL VERIFICATION RESULTS FOR MILESTONE 4 ===")
    req_res = test_requirements_txt_deep()
    print("\n1. requirements.txt Verification:")
    print(req_res)

    env_res = test_env_example_deep()
    print("\n2. .env.example Verification:")
    print(env_res)

    wf_res = test_github_workflow_and_batch_scripts()
    print("\n3. CI/CD & Batch Scripts Verification:")
    print(wf_res)
